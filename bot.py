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
    "hotspot": {"name": "Hotspot Shield 7D", "price": 2000},
    "gemini": {"name": "Gemini Pro 30D", "price": 50000}
}

# Collection lưu trạng thái category (enabled/disabled)
categories_collection = db['categories']

# Khởi tạo mặc định nếu chưa có
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

# ================== CHỐNG DUPLICATE ==================
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
            
            # Tự động bật lại sản phẩm nếu trước đó bị ẩn do hết hàng
            categories_collection.update_one(
                {"code": cat},
                {"$set": {"enabled": True}}
            )
            
            bot.reply_to(message, f"✅ Đã thêm **{added_count}** tài khoản vào {CATEGORIES[cat]['name']}!\nSản phẩm đã được mở bán lại.")
            return
    
    bot.reply_to(message, "❌ Không nhận diện được loại tài khoản từ tên file!")

# ================== LỆNH TOGGLE KHÓA/MỞ SẢN PHẨM ==================
@bot.message_handler(commands=['toggle'])
def toggle_product(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin dùng lệnh này!")
    
    try:
        code = message.text.split()[1].lower()
        if code not in CATEGORIES:
            return bot.reply_to(message, f"❌ Mã sản phẩm không hợp lệ. Các mã: {', '.join(CATEGORIES.keys())}")
        
        current = categories_collection.find_one({"code": code})
        new_status = not current.get("enabled", True)
        
        categories_collection.update_one(
            {"code": code},
            {"$set": {"enabled": new_status}}
        )
        
        status_text = "MỞ BÁN" if new_status else "KHÓA"
        bot.reply_to(message, f"✅ Đã **{status_text}** sản phẩm {CATEGORIES[code]['name']} ({code})")
    except IndexError:
        bot.reply_to(message, "Sử dụng: /toggle <mã sản phẩm>\nVí dụ: /toggle spotify")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

# ================== MENU MUA HÀNG (TỰ ĐỘNG ẨN KHI HẾT HÀNG / KHÓA) ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    
    has_available = False
    for code, info in CATEGORIES.items():
        # Kiểm tra trạng thái enabled
        cat_doc = categories_collection.find_one({"code": code})
        enabled = cat_doc.get("enabled", True) if cat_doc else True
        
        # Kiểm tra stock thực tế
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
        bot.send_message(message.chat.id, "Hiện tại tất cả sản phẩm đang hết hàng hoặc bị khóa. Vui lòng quay lại sau nhé! 😔")
        return
    
    bot.send_message(message.chat.id, "👋 Chào bạn! Chọn tài khoản Pro bạn muốn mua:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("info_outofstock_"))
def handle_outofstock_info(call):
    code = call.data.split("_")[2]
    info = CATEGORIES.get(code, {})
    bot.answer_callback_query(call.id, text=f"{info.get('name', 'Sản phẩm')} hiện đang hết hàng hoặc tạm khóa. Admin sẽ cập nhật sớm!", show_alert=True)

# ================== XỬ LÝ MUA HÀNG ==================
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

Mở link để xem QR code lớn hoặc chuyển khoản theo hướng dẫn.
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

# ================== ADMIN GIAO TÀI KHOẢN (TỰ ĐỘNG LẤY TỪ STOCK) ==================
@bot.message_handler(func=lambda m: m.text and m.text.strip().upper().startswith("GIAO"))
def handle_delivery(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) < 2:
            return bot.reply_to(message, "❌ Format: GIAO <mã đơn>\nVí dụ: GIAO 12345678")

        order_code = int(parts[1].strip())

        order = db.orders.find_one({"order_code": order_code, "status": "pending"})
        if not order:
            return bot.reply_to(message, "❌ Không tìm thấy đơn pending!")

        category = order["category"]
        user_id = order["user_id"]

        stock_doc = db.stocks.find_one({"category": category})
        if not stock_doc or not stock_doc.get("accounts"):
            bot.send_message(ADMIN_ID, f"⚠️ HẾT STOCK {CATEGORIES[category]['name']}! Đơn #{order_code} chưa giao.")
            bot.send_message(user_id, "⏳ Tài khoản tạm hết, admin đang bổ sung. Xin lỗi vì sự chậm trễ!")
            return bot.reply_to(message, f"❌ Hết stock {CATEGORIES[category]['name']}!")

        # Lấy và xóa 1 tài khoản đầu tiên
        account = stock_doc["accounts"][0]
        db.stocks.update_one(
            {"category": category},
            {"$pop": {"accounts": -1}}
        )

        # Gửi cho user
        buyer_text = f"""
🎉 Tài khoản đã được giao!

Đơn: #{order_code}
Sản phẩm: {CATEGORIES[category]['name']}
Tài khoản:
{account}

Cảm ơn bạn! ❤️
        """
        bot.send_message(user_id, buyer_text)

        # Cập nhật đơn
        db.orders.update_one(
            {"order_code": order_code},
            {"$set": {"status": "delivered", "delivered_at": datetime.now(), "account": account}}
        )

        remaining = len(stock_doc["accounts"]) - 1
        bot.reply_to(message, f"✅ Giao thành công đơn #{order_code}\nCòn lại: {remaining} tk")

        # Nếu còn ít → cảnh báo admin
        if remaining <= 5:
            bot.send_message(ADMIN_ID, f"⚠️ Stock {CATEGORIES[category]['name']} sắp hết! Chỉ còn {remaining} tài khoản.")

        # Nếu hết hẳn → tắt enabled
        if remaining == 0:
            categories_collection.update_one(
                {"code": category},
                {"$set": {"enabled": False}}
            )
            bot.send_message(ADMIN_ID, f"🔒 Đã tự động khóa {CATEGORIES[category]['name']} vì hết hàng.")

    except ValueError:
        bot.reply_to(message, "❌ Mã đơn phải là số!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")
        print("Lỗi giao:", str(e))

# ================== CHẠY BOT ==================
print("🤖 Bot đang chạy...")
bot.infinity_polling()
