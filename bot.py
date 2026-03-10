import telebot
import random
import os
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from payos import PayOS
from payos.types import CreatePaymentLinkRequest
from flask import Flask, request, abort
import threading
import time

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
    "hotspot": {"name": "Hotspot Shield 7D", "price": 2000},
    "gemini": {"name": "Gemini Pro 1 Acc Duy Nhất 26-29D", "price": 40000}
}


# Collection lưu trạng thái category
categories_collection = db['categories']

# Khởi tạo mặc định
for code in CATEGORIES:
    categories_collection.update_one(
        {"code": code},
        {"$setOnInsert": {
            "code": code,
            "name": CATEGORIES[code]["name"],
            "price": CATEGORIES[code]["price"],
            "enabled": True
        }},
        upsert=True
    )

processed_callbacks = set()

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
    bot.send_message(call.message.chat.id, f"📤 Gửi file TXT chứa tài khoản {CATEGORIES[category]['name']}\n(Mỗi dòng 1 tài khoản)")
    processed_callbacks.add(call.id)

@bot.message_handler(content_types=['document'])
def handle_document(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    file_info = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path)
    accounts = [line.decode('utf-8').strip() for line in downloaded.splitlines() if line.strip()]
    
    for cat in CATEGORIES:
        if cat.lower() in message.document.file_name.lower():
            add_to_stock(cat, accounts)
            added_count = len(accounts)
            
            categories_collection.update_one(
                {"code": cat},
                {"$set": {"enabled": True}}
            )
            
            bot.reply_to(message, f"✅ Đã thêm **{added_count}** tài khoản vào {CATEGORIES[cat]['name']}!\nSản phẩm đã được mở bán lại.")
            return
    
    bot.reply_to(message, "❌ Không nhận diện được loại tài khoản từ tên file!")

# ================== TOGGLE ==================
@bot.message_handler(commands=['toggle'])
def toggle_product(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin dùng lệnh này!")
    
    try:
        code = message.text.split()[1].lower()
        if code not in CATEGORIES:
            return bot.reply_to(message, f"❌ Mã không hợp lệ: {', '.join(CATEGORIES.keys())}")
        
        current = categories_collection.find_one({"code": code})
        new_status = not current.get("enabled", True)
        
        categories_collection.update_one(
            {"code": code},
            {"$set": {"enabled": new_status}}
        )
        
        status_text = "MỞ BÁN" if new_status else "KHÓA"
        bot.reply_to(message, f"✅ Đã **{status_text}** {CATEGORIES[code]['name']} ({code})")
    except IndexError:
        bot.reply_to(message, "Sử dụng: /toggle <mã>\nVí dụ: /toggle spotify")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

# ================== MENU START ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    has_available = False
    
    for code, info in CATEGORIES.items():
        cat_doc = categories_collection.find_one({"code": code})
        enabled = cat_doc.get("enabled", True) if cat_doc else True
        
        stock_doc = db.stocks.find_one({"category": code})
        stock_count = len(stock_doc.get("accounts", [])) if stock_doc else 0
        
        if enabled and stock_count > 0:
            has_available = True
            markup.add(telebot.types.InlineKeyboardButton(
                f"🛒 Mua {info['name']} - {info['price']:,}đ (còn {stock_count})",
                callback_data=f"buy_{code}"
            ))
        else:
            status_text = "🔒 Hết hàng" if stock_count == 0 else "🔧 Tạm khóa"
            markup.add(telebot.types.InlineKeyboardButton(
                f"{info['name']} - {status_text}",
                callback_data=f"info_outofstock_{code}"
            ))
    
    if not has_available:
        bot.send_message(message.chat.id, "Hiện tại tất cả sản phẩm đang hết hoặc bị khóa. Vui lòng quay lại sau! 😔")
        return
    
    bot.send_message(message.chat.id, "👋 Chào bạn! Chọn tài khoản Pro bạn muốn mua:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("info_outofstock_"))
def handle_outofstock_info(call):
    code = call.data.split("_")[2]
    info = CATEGORIES.get(code, {})
    bot.answer_callback_query(call.id, text=f"{info.get('name', 'Sản phẩm')} hiện đang hết hàng hoặc tạm khóa. Admin sẽ cập nhật sớm!", show_alert=True)

# ================== MUA HÀNG ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    if call.id in processed_callbacks:
        bot.answer_callback_query(call.id, text="✅ Đơn đã tạo!", show_alert=False)
        return
    processed_callbacks.add(call.id)

    try:
        category = call.data.split("_")[1]
        info = CATEGORIES[category]
        order_code = generate_order_code()

        db.orders.insert_one({
            "order_code": order_code,
            "user_id": call.from_user.id,
            "username": call.from_user.username or call.from_user.first_name,
            "category": category,
            "amount": info["price"],
            "status": "pending",
            "created_at": datetime.now()
        })

        payment_data = CreatePaymentLinkRequest(
            order_code=order_code,
            amount=info["price"],
            description=f"Don {order_code}",
            return_url="https://t.me/" + bot.get_me().username,
            cancel_url="https://t.me/" + bot.get_me().username
        )
        payment_link = payos.payment_requests.create(payment_data)

        text = f"""
✅ Đơn hàng #{order_code} đã tạo!

💰 Số tiền: {info['price']:,}đ
📦 Sản phẩm: {info['name']}

🔗 Thanh toán ngay:
{payment_link.checkout_url}

Mở link để xem QR hoặc chuyển khoản.
        """
        bot.send_message(call.message.chat.id, text)

        admin_text = f"""
🛒 ĐƠN MỚI!
Mã: #{order_code}
Người: @{call.from_user.username or call.from_user.first_name} ({call.from_user.id})
Sản phẩm: {info['name']}
Giá: {info['price']:,}đ
Link: {payment_link.checkout_url}
        """
        bot.send_message(ADMIN_ID, admin_text)

        bot.answer_callback_query(call.id, text="Đơn hàng đã tạo!", show_alert=False)

    except Exception as e:
        bot.answer_callback_query(call.id, text="❌ Lỗi: " + str(e)[:100], show_alert=True)
        print("Lỗi tạo đơn:", str(e))

# ================== GIAO TÀI KHOẢN ==================
@bot.message_handler(func=lambda m: m.text and m.text.strip().upper().startswith("GIAO"))
def handle_delivery(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) < 2:
            return bot.reply_to(message, "❌ Format: GIAO <mã đơn>")

        order_code = int(parts[1].strip())

        order = db.orders.find_one({"order_code": order_code, "status": "pending"})
        if not order:
            return bot.reply_to(message, "❌ Không tìm thấy đơn pending!")

        category = order["category"]
        user_id = order["user_id"]

        stock_doc = db.stocks.find_one({"category": category})
        if not stock_doc or not stock_doc.get("accounts"):
            bot.send_message(ADMIN_ID, f"⚠️ HẾT STOCK {CATEGORIES[category]['name']}! Đơn #{order_code}")
            bot.send_message(user_id, "⏳ Tài khoản tạm hết, admin đang bổ sung.")
            return bot.reply_to(message, f"❌ Hết stock {CATEGORIES[category]['name']}!")

        account = stock_doc["accounts"][0]
        db.stocks.update_one(
            {"category": category},
            {"$pop": {"accounts": -1}}
        )

        buyer_text = f"""
🎉 Tài khoản đã giao!

Đơn: #{order_code}
Sản phẩm: {CATEGORIES[category]['name']}
Tài khoản:
{account}

Cảm ơn bạn! ❤️
        """
        bot.send_message(user_id, buyer_text)

        db.orders.update_one(
            {"order_code": order_code},
            {"$set": {"status": "delivered", "delivered_at": datetime.now(), "account": account}}
        )

        remaining = len(stock_doc["accounts"]) - 1
        bot.reply_to(message, f"✅ Giao thành công #{order_code} | Còn: {remaining}")

        if remaining <= 5:
            bot.send_message(ADMIN_ID, f"⚠️ Stock {CATEGORIES[category]['name']} sắp hết! Còn {remaining}")

        if remaining == 0:
            categories_collection.update_one(
                {"code": category},
                {"$set": {"enabled": False}}
            )
            bot.send_message(ADMIN_ID, f"🔒 Tự động khóa {CATEGORIES[category]['name']} vì hết hàng.")

    except ValueError:
        bot.reply_to(message, "❌ Mã đơn phải là số!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")
        print("Lỗi giao:", str(e))

# ================== FLASK + POLLING CHO RENDER ==================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is alive on Render!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    print(f"Flask listening on 0.0.0.0:{port}")
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Chạy Flask trong thread riêng
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)  # Đợi Flask khởi động

    print("🤖 Bot đang chạy... (với Flask cho Render + retry polling)")

    while True:
        try:
            bot.remove_webhook()  # Đảm bảo không dùng webhook cũ
            bot.infinity_polling(timeout=20, long_polling_timeout=50)
        except telebot.apihelper.ApiTelegramException as e:
            if "terminated by other getUpdates" in str(e):
                print("Conflict 409 detected → retry sau 10 giây...")
                time.sleep(10)
            else:
                print("Lỗi Telegram API:", str(e))
                time.sleep(5)
        except Exception as e:
            print("Polling lỗi:", str(e))
            time.sleep(5)

