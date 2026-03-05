import telebot
import random
import os
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from payos import PayOS
from payos.types import CreatePaymentLinkRequest

load_dotenv()

# ================== CẤU HÌNH ==================
bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))
payos = PayOS(
    client_id=os.getenv('PAYOS_CLIENT_ID'),
    api_key=os.getenv('PAYOS_API_KEY'),
    checksum_key=os.getenv('PAYOS_CHECKSUM_KEY')
)
client = MongoClient(os.getenv('MONGO_URI'))
db = client['ban_taikhoan_pro']

ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Danh sách loại tài khoản + giá (bạn có thể sửa thoải mái)
CATEGORIES = {
    "capcut": {"name": "CapCut Premium 7D", "price": 2000},
    "hotspot": {"name": "Hotspot Shield 7D", "price": 2000}
}

# ================== CHỐNG DUPLICATE ĐƠN HÀNG ==================
processed_callbacks = set()  # Lưu ID của callback đã xử lý

# ================== HÀM HỖ TRỢ ==================
def generate_order_code():
    return random.randint(10000000, 99999999)

def add_to_stock(category, accounts_list):
    db.stocks.update_one(
        {"category": category},
        {"$push": {"accounts": {"$each": accounts_list}}},
        upsert=True
    )

# ================== ADMIN PANEL ==================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Bạn không phải admin!")
    
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    for code, info in CATEGORIES.items():
        markup.add(telebot.types.InlineKeyboardButton(
            f"📥 Cập nhật {info['name']}", callback_data=f"update_{code}"
        ))
    bot.send_message(message.chat.id, "🔧 Chọn loại tài khoản cần cập nhật stock:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("update_"))
def handle_update_stock(call):
    if call.from_user.id != ADMIN_ID:
        return
    category = call.data.split("_")[1]
    bot.send_message(call.message.chat.id, f"📤 Gửi file TXT chứa tài khoản {CATEGORIES[category]['name']}\n(Mỗi dòng 1 tài khoản, ví dụ: email:pass)")
    
    processed_callbacks.add(call.id)  # tránh lặp

@bot.message_handler(content_types=['document'])
def handle_document(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    file_info = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path)
    accounts = [line.decode('utf-8').strip() for line in downloaded.splitlines() if line.strip()]
    
    # Tự động phát hiện category từ tên file (có thể cải tiến sau)
    for cat in CATEGORIES:
        if cat.lower() in message.document.file_name.lower():
            add_to_stock(cat, accounts)
            bot.reply_to(message, f"✅ Đã thêm **{len(accounts)}** tài khoản vào {CATEGORIES[cat]['name']}!")
            return
    bot.reply_to(message, "❌ Không nhận diện được loại tài khoản từ tên file!")

# ================== USER MUA HÀNG ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    for code, info in CATEGORIES.items():
        markup.add(telebot.types.InlineKeyboardButton(
            f"🛒 Mua {info['name']} - {info['price']:,}đ", callback_data=f"buy_{code}"
        ))
    bot.send_message(message.chat.id, "👋 Chào bạn! Chọn tài khoản Pro bạn muốn mua:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    if call.id in processed_callbacks:
        bot.answer_callback_query(call.id, text="✅ Đơn đã được tạo!", show_alert=False)
        return
    processed_callbacks.add(call.id)

    try:
        category = call.data.split("_")[1]
        info = CATEGORIES[category]
        order_code = generate_order_code()

        # Lưu đơn hàng
        db.orders.insert_one({
            "order_code": order_code,
            "user_id": call.from_user.id,
            "username": call.from_user.username or call.from_user.first_name,
            "category": category,
            "amount": info["price"],
            "status": "pending",
            "created_at": datetime.now()
        })

        # Tạo link PayOS
        payment_data = CreatePaymentLinkRequest(
            order_code=order_code,
            amount=info["price"],
            description=f"Don {order_code}",
            return_url="https://t.me/" + bot.get_me().username,
            cancel_url="https://t.me/" + bot.get_me().username
        )
        payment_link = payos.payment_requests.create(payment_data)

        # Tin nhắn gửi cho người dùng (không gửi ảnh QR nữa)
        text = f"""
✅ Đơn hàng #{order_code} đã tạo thành công!

💰 Số tiền: {info['price']:,}đ
📦 Sản phẩm: {info['name']}

🔗 Thanh toán ngay tại đây:
{payment_link.checkout_url}

📲 Mở link → trang sẽ hiển thị mã QR  để quét hoặc thông tin chuyển khoản.
Sau khi thanh toán thành công, admin sẽ gửi tài khoản cho bạn trong vài phút, nếu có vấn đề gì hãy liên hệ admin nhé! ❤️
        """
        bot.send_message(call.message.chat.id, text)

        # Thông báo cho admin
        admin_text = f"""
🛒 ĐƠN HÀNG MỚI!
Mã đơn: #{order_code}
Người mua: @{call.from_user.username or call.from_user.first_name} ({call.from_user.id})
Sản phẩm: {info['name']}
Số tiền: {info['price']:,}đ
Link thanh toán: {payment_link.checkout_url}
        """
        bot.send_message(ADMIN_ID, admin_text)

        bot.answer_callback_query(call.id, text="Đơn hàng đã tạo!", show_alert=False)

    except Exception as e:
        bot.answer_callback_query(call.id, text="❌ Lỗi xảy ra, thử lại sau", show_alert=True)
        print("Lỗi tạo đơn:", str(e))

# ================== ADMIN GIAO TÀI KHOẢN ==================
@bot.message_handler(func=lambda m: m.text and m.text.strip().upper().startswith("GIAO"))
def handle_delivery(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        # Lấy mã đơn từ tin nhắn
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) < 2:
            return bot.reply_to(message, "❌ Format: GIAO <mã đơn>\nVí dụ: GIAO 12345678")

        order_code_str = parts[1].strip()
        order_code = int(order_code_str)

        # Tìm đơn hàng pending
        order = db.orders.find_one({"order_code": order_code, "status": "pending"})
        if not order:
            return bot.reply_to(message, "❌ Không tìm thấy đơn hàng pending với mã này hoặc đã giao rồi!")

        category = order["category"]
        user_id = order["user_id"]

        # Tìm stock của category
        stock_doc = db.stocks.find_one({"category": category})
        if not stock_doc or not stock_doc.get("accounts") or len(stock_doc["accounts"]) == 0:
            bot.send_message(ADMIN_ID, f"⚠️ HẾT TÀI KHOẢN {CATEGORIES[category]['name']}!\nĐơn #{order_code} chưa giao được.")
            bot.send_message(user_id, "⏳ Đơn hàng của bạn đang chờ xử lý. Tài khoản tạm hết, admin sẽ bổ sung sớm. Xin lỗi vì sự chậm trễ!")
            return bot.reply_to(message, f"❌ Hết stock {CATEGORIES[category]['name']}! Đơn #{order_code} chưa giao.")

        # Lấy và xóa 1 tài khoản đầu tiên (FIFO)
        account = stock_doc["accounts"][0]
        db.stocks.update_one(
            {"category": category},
            {"$pop": {"accounts": -1}}   # -1 = pop từ đầu mảng
        )

        # Gửi cho người mua
        buyer_text = f"""
🎉 Tài khoản của bạn đã được giao thành công!

Đơn hàng: #{order_code}
Sản phẩm: {CATEGORIES[category]['name']}
Tài khoản:
{account}

Lưu ý: Đừng chia sẻ tài khoản với ai nhé! ❤️
        """
        bot.send_message(user_id, buyer_text)

        # Cập nhật trạng thái đơn
        db.orders.update_one(
            {"order_code": order_code},
            {"$set": {
                "status": "delivered",
                "delivered_at": datetime.now(),
                "account_delivered": account
            }}
        )

        bot.reply_to(message, f"✅ Đã giao thành công đơn #{order_code}\nTài khoản: {account}\nCòn lại: {len(stock_doc['accounts']) - 1} tk")

        # Nếu sau khi pop còn ít hơn 5 tài khoản → cảnh báo admin
        remaining = len(stock_doc["accounts"]) - 1
        if remaining <= 5:
            bot.send_message(ADMIN_ID, f"⚠️ Stock {CATEGORIES[category]['name']} sắp hết! Chỉ còn {remaining} tài khoản.")

    except ValueError:
        bot.reply_to(message, "❌ Mã đơn phải là số! Ví dụ: GIAO 12345678")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi xử lý: {str(e)}")
        print("Lỗi giao hàng:", str(e))
        from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
# ================== CHẠY BOT ==================
print("🤖 Bot đang chạy... (chỉ gửi link PayOS, không gửi ảnh QR)")

bot.infinity_polling()
