import telebot
import random
import os
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from payos import PayOS
from payos.types import CreatePaymentLinkRequest
from flask import Flask, request
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

ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

# Collections
users = db['users']
orders = db['orders']
stocks = db['stocks']
categories = db['categories']

# Categories (đã tách Canva)
CATEGORIES = {
    "hotspot": {"name": "Hotspot Shield 7D", "price": 2000, "type": "normal"},
    "gemini": {"name": "Gemini Pro 1 Acc 26-29D", "price": 40000, "type": "normal"},
    "capcut": {"name": "CapCut Pro 1 Tuần", "price": 2000, "type": "normal"},
    "canva1slot": {"name": "Canva 1 Slot", "price": 2000, "type": "canva_1slot"},
    "canva100slot": {"name": "Canva 100 Slot", "price": 30000, "type": "normal"},
}

# Khởi tạo categories
for code, info in CATEGORIES.items():
    categories.update_one(
        {"code": code},
        {"$setOnInsert": {
            "code": code,
            "name": info["name"],
            "price": info["price"],
            "type": info.get("type", "normal"),
            "enabled": True
        }},
        upsert=True
    )

# ================== HÀM HỖ TRỢ ==================
def get_user(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "username": None,
            "first_name": None,
            "balance": 0,
            "joined_at": datetime.now()
        }
        users.insert_one(user)
    return user

def update_balance(user_id, amount):
    users.update_one({"user_id": user_id}, {"$inc": {"balance": amount}})

def generate_order_code():
    return random.randint(10000000, 99999999)

def add_to_stock(category, accounts_list):
    stocks.update_one(
        {"category": category},
        {"$push": {"accounts": {"$each": accounts_list}}},
        upsert=True
    )
    # Tự động mở bán lại khi có stock
    categories.update_one({"code": category}, {"$set": {"enabled": True}})

# ================== COMMANDS ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    has_available = False

    for code, info in CATEGORIES.items():
        cat_doc = categories.find_one({"code": code})
        enabled = cat_doc.get("enabled", True) if cat_doc else True

        stock_doc = stocks.find_one({"category": code})
        stock_count = len(stock_doc.get("accounts", [])) if stock_doc else 0

        if enabled and stock_count > 0:
            has_available = True
            markup.add(telebot.types.InlineKeyboardButton(
                f"🛒 Mua {info['name']} - {info['price']:,}đ (còn {stock_count})",
                callback_data=f"buy_{code}"
            ))
        else:
            status = "🔒 Hết hàng" if stock_count == 0 else "🔧 Tạm khóa"
            markup.add(telebot.types.InlineKeyboardButton(
                f"{info['name']} - {status}",
                callback_data=f"info_outofstock_{code}"
            ))

    markup.add(telebot.types.InlineKeyboardButton("💰 Ví của tôi", callback_data="my_wallet"))
    markup.add(telebot.types.InlineKeyboardButton("💳 Nạp tiền vào ví", callback_data="deposit"))

    if not has_available:
        bot.send_message(message.chat.id, "Hiện tại tất cả sản phẩm đang hết hoặc bị khóa. Vui lòng quay lại sau! 😔", reply_markup=markup)
        return

    bot.send_message(message.chat.id, 
        f"👋 Chào **{message.from_user.first_name}**!\n\nChọn sản phẩm bạn muốn mua:", 
        parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(commands=['me', 'info'])
def show_info(message):
    user = get_user(message.from_user.id)
    joined = user.get('joined_at', datetime.now()).strftime('%d/%m/%Y %H:%M')

    text = f"""
🆔 **ID:** `{message.from_user.id}`
👤 **Tên:** {message.from_user.first_name or message.from_user.username or 'Không có tên'}
💰 **Số dư:** `{user.get('balance', 0):,}đ`
📅 **Tham gia:** {joined}
    """
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ================== ADMIN COMMANDS ==================
@bot.message_handler(commands=['users', 'balance'])
def admin_view_balances(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng lệnh này!")

    all_users = users.find().sort("balance", -1)
    text = "📊 **DANH SÁCH SỐ DƯ USER**\n\n"
    for u in all_users:
        username = u.get('username') or u.get('first_name') or 'Unknown'
        text += f"👤 {username} (ID: `{u['user_id']}`) → 💰 `{u.get('balance', 0):,}đ`\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['duyetnap'])
def admin_duyet_nap(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng lệnh này!")

    try:
        order_code = int(message.text.split()[1])
        order = orders.find_one({"order_code": order_code, "type": "deposit", "status": "pending"})
        if not order:
            return bot.reply_to(message, "❌ Không tìm thấy đơn nạp pending!")

        user_id = order['user_id']
        amount = order['amount']

        update_balance(user_id, amount)
        orders.update_one({"order_code": order_code}, {"$set": {"status": "approved", "approved_at": datetime.now()}})

        bot.send_message(user_id, f"✅ **Nạp tiền đã được duyệt!**\nSố tiền: +{amount:,}đ\nSố dư hiện tại: {get_user(user_id)['balance']:,}đ")
        bot.reply_to(message, f"✅ Đã duyệt nạp tiền #{order_code} - Cộng {amount:,}đ")

    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['giao'])
def admin_giao_tai_khoan(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng lệnh này!")

    try:
        order_code = int(message.text.split()[1])
        order = orders.find_one({"order_code": order_code, "status": "pending"})

        if not order or order['type'] != 'purchase':
            return bot.reply_to(message, "❌ Không tìm thấy đơn mua pending!")

        category = order['category']
        user_id = order['user_id']

        stock_doc = stocks.find_one({"category": category})
        if not stock_doc or not stock_doc.get("accounts"):
            return bot.reply_to(message, "❌ Hết stock loại này!")

        account = stock_doc["accounts"].pop(0)
        stocks.update_one({"category": category}, {"$set": {"accounts": stock_doc["accounts"]}})

        bot.send_message(user_id, f"""
🎉 **Tài khoản đã được giao thủ công!**

Đơn: #{order_code}
Sản phẩm: {CATEGORIES[category]['name']}
Tài khoản: {account}
        """)

        orders.update_one({"order_code": order_code}, {"$set": {"status": "delivered", "delivered_at": datetime.now(), "account": account}})

        bot.reply_to(message, f"✅ Đã giao thành công đơn #{order_code}")

    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['resetbalance'])
def admin_reset_balance(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng lệnh này!")

    try:
        user_id = int(message.text.split()[1])
        update_balance(user_id, -get_user(user_id)['balance'])
        bot.reply_to(message, f"✅ Đã reset số dư user `{user_id}` về 0đ")
    except:
        bot.reply_to(message, "Sử dụng: /resetbalance <user_id>")

@bot.message_handler(commands=['resetallbalance'])
def admin_reset_all_balance(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng lệnh này!")

    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ Xác nhận reset tất cả", callback_data="confirm_reset_all"))
    markup.add(telebot.types.InlineKeyboardButton("❌ Hủy", callback_data="cancel_reset_all"))

    bot.reply_to(message, "⚠️ Bạn sắp reset số dư về 0 cho **TẤT CẢ** user. Xác nhận?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_reset_all", "cancel_reset_all"])
def handle_reset_all(call):
    if call.from_user.id != ADMIN_ID:
        return
    if call.data == "cancel_reset_all":
        bot.edit_message_text("Đã hủy.", call.message.chat.id, call.message.message_id)
        return
    users.update_many({}, {"$set": {"balance": 0}})
    bot.edit_message_text("✅ Đã reset số dư về 0 cho tất cả user.", call.message.chat.id, call.message.message_id)

# ================== MUA HÀNG ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    code = call.data.split("_")[1]
    info = CATEGORIES.get(code)
    if not info:
        return bot.answer_callback_query(call.id, "Sản phẩm không tồn tại!")

    # Kiểm tra stock
    stock_doc = stocks.find_one({"category": code})
    stock_count = len(stock_doc.get("accounts", [])) if stock_doc else 0

    if stock_count == 0:
        return bot.answer_callback_query(call.id, "❌ Sản phẩm đã hết hàng!", show_alert=True)

    user = get_user(call.from_user.id)
    price = info["price"]

    if user.get("balance", 0) >= price:
        # Trừ tiền ví và giao ngay
        update_balance(call.from_user.id, -price)
        account = stock_doc["accounts"].pop(0)
        stocks.update_one({"category": code}, {"$set": {"accounts": stock_doc["accounts"]}})

        bot.send_message(call.from_user.id, f"""
🎉 **Mua thành công từ ví!**

Sản phẩm: {info['name']}
Tài khoản: {account}
Số dư còn lại: {user['balance'] - price:,}đ
        """)
    else:
        # Tạo link PayOS
        order_code = generate_order_code()
        orders.insert_one({
            "order_code": order_code,
            "user_id": call.from_user.id,
            "category": code,
            "amount": price,
            "type": "purchase",
            "status": "pending",
            "created_at": datetime.now()
        })

        payment_data = CreatePaymentLinkRequest(
            order_code=order_code,
            amount=price,
            description=f"Don {order_code}",
            return_url="https://t.me/" + bot.get_me().username,
            cancel_url="https://t.me/" + bot.get_me().username
        )
        payment_link = payos.payment_requests.create(payment_data)

        bot.send_message(call.from_user.id, f"""
✅ Đơn hàng #{order_code} đã tạo!

💰 Số tiền: {price:,}đ
📦 Sản phẩm: {info['name']}

🔗 Thanh toán ngay: {payment_link.checkout_url}
        """)

    bot.answer_callback_query(call.id)

# ================== FLASK + POLLING ==================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is alive on Render!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)

    print("🤖 Bot đang chạy...")

    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=50)
        except Exception as e:
            print("Polling lỗi:", str(e))
            time.sleep(5)
