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

users = db['users']
orders = db['orders']
stocks = db['stocks']
categories = db['categories']

CATEGORIES = {
    "hotspot": {"name": "Hotspot Shield 7D", "price": 2000, "type": "normal"},
    "gemini": {"name": "Gemini Pro 1 Acc 26-29D", "price": 40000, "type": "normal"},
    "capcut": {"name": "CapCut Pro 1 Tuần", "price": 2000, "type": "normal"},
    "canva1slot": {"name": "Canva 1 Slot", "price": 2000, "type": "canva_1slot"},
    "canva100slot": {"name": "Canva 100 Slot", "price": 30000, "type": "normal"},
}

# Khởi tạo categories
for code, info in CATEGORIES.items():
    categories.update_one({"code": code}, {"$setOnInsert": {
        "code": code, "name": info["name"], "price": info["price"], "type": info.get("type", "normal"), "enabled": True
    }}, upsert=True)

def get_user(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        user = {"user_id": user_id, "username": None, "first_name": None, "balance": 0, "joined_at": datetime.now()}
        users.insert_one(user)
    return user

def update_balance(user_id, amount):
    users.update_one({"user_id": user_id}, {"$inc": {"balance": amount}})

def generate_order_code():
    return random.randint(10000000, 99999999)

def get_stock_count(category):
    stock_doc = stocks.find_one({"category": category})
    return len(stock_doc.get("accounts", [])) if stock_doc else 0

# ================== START MENU ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    for code, info in CATEGORIES.items():
        stock_count = get_stock_count(code)
        if stock_count > 0:
            markup.add(telebot.types.InlineKeyboardButton(
                f"🛒 Mua {info['name']} - {info['price']:,}đ (còn {stock_count})",
                callback_data=f"buy_{code}"
            ))
        else:
            markup.add(telebot.types.InlineKeyboardButton(
                f"{info['name']} - 🔒 Hết hàng",
                callback_data="info_outofstock"
            ))

    markup.add(telebot.types.InlineKeyboardButton("💰 Ví của tôi", callback_data="my_wallet"))
    markup.add(telebot.types.InlineKeyboardButton("💳 Nạp tiền vào ví", callback_data="deposit"))

    bot.send_message(message.chat.id, f"👋 Chào **{message.from_user.first_name}**!\n\nChọn sản phẩm:", 
                     parse_mode='Markdown', reply_markup=markup)

# ================== CALLBACK HANDLER CHUNG (FIX KHÔNG PHẢN HỒI) ==================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)   # Luôn trả lời callback để tránh Telegram block
    try:
        data = call.data
        if data == "my_wallet":
            show_wallet(call)
        elif data == "deposit":
            deposit_menu(call)
        elif data.startswith("deposit_"):
            handle_deposit(call)
        elif data.startswith("buy_"):
            handle_buy(call)
        elif data == "info_outofstock":
            bot.send_message(call.message.chat.id, "❌ Sản phẩm hiện đang hết hàng!")
    except Exception as e:
        print("Callback error:", str(e))
        bot.send_message(call.message.chat.id, "❌ Có lỗi xảy ra!")

# ================== XEM VÍ & NẠP TIỀN ==================
def show_wallet(call):
    user = get_user(call.from_user.id)
    joined = user.get('joined_at', datetime.now()).strftime('%d/%m/%Y %H:%M')
    text = f"🆔 **ID:** `{call.from_user.id}`\n👤 **Tên:** {call.from_user.first_name or 'Không có tên'}\n💰 **Số dư:** `{user.get('balance', 0):,}đ`\n📅 **Tham gia:** {joined}"
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

def deposit_menu(call):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("50.000đ", callback_data="deposit_50000"))
    markup.add(telebot.types.InlineKeyboardButton("100.000đ", callback_data="deposit_100000"))
    markup.add(telebot.types.InlineKeyboardButton("200.000đ", callback_data="deposit_200000"))
    markup.add(telebot.types.InlineKeyboardButton("Nhập số khác", callback_data="deposit_custom"))
    bot.send_message(call.message.chat.id, "💳 Chọn số tiền nạp:", reply_markup=markup)

# (Phần nạp tiền giữ nguyên như cũ - handle_deposit, process_custom_deposit)

# ================== MUA HÀNG - CANVA 1 SLOT (ĐÃ SỬA TRỪ STOCK) ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    code = call.data.split("_")[1]
    info = CATEGORIES.get(code)
    if not info:
        return bot.send_message(call.message.chat.id, "Sản phẩm không tồn tại!")

    user = get_user(call.from_user.id)
    price = info["price"]

    if code == "canva1slot":
        stock_count = get_stock_count("canva1slot")
        if stock_count <= 0:
            return bot.send_message(call.message.chat.id, "❌ Canva 1 Slot đã hết hàng!")

        if user.get("balance", 0) < price:
            return bot.send_message(call.message.chat.id, f"❌ Số dư ví không đủ!\nCần {price:,}đ\nHiện có: {user.get('balance', 0):,}đ\n\nVui lòng nạp tiền trước.")

        # Trừ tiền ví
        update_balance(call.from_user.id, -price)

        # Tạo đơn chờ email và trừ stock ngay
        order_code = generate_order_code()
        orders.insert_one({
            "order_code": order_code,
            "user_id": call.from_user.id,
            "category": "canva1slot",
            "amount": price,
            "type": "canva_1slot",
            "status": "waiting_email",
            "created_at": datetime.now()
        })

        # Trừ 1 slot Canva 1 Slot
        stock_doc = stocks.find_one({"category": "canva1slot"})
        if stock_doc and stock_doc.get("accounts"):
            stock_doc["accounts"].pop(0)
            stocks.update_one({"category": "canva1slot"}, {"$set": {"accounts": stock_doc["accounts"]}})

        bot.send_message(call.message.chat.id, f"""
✅ **Đã trừ {price:,}đ từ ví!**

Sản phẩm: Canva 1 Slot
Số dư còn lại: {user['balance'] - price:,}đ

📧 Vui lòng gửi **email Canva** của bạn ngay bây giờ.
Bot sẽ chuyển cho admin để thêm vào slot.
        """)
        return

    # Các sản phẩm khác (giữ nguyên)
    # ... (code mua từ ví hoặc tạo link PayOS)

# ================== XỬ LÝ EMAIL CANVA 1 SLOT ==================
@bot.message_handler(func=lambda m: True)
def handle_user_message(message):
    pending = orders.find_one({"user_id": message.from_user.id, "type": "canva_1slot", "status": "waiting_email"})
    if pending:
        email = message.text.strip()
        admin_msg = f"""
📨 **CANVA 1 SLOT - CHỜ THÊM**

Mã đơn: #{pending['order_code']}
User: {message.from_user.id}
Email: {email}
        """
        bot.send_message(ADMIN_ID, admin_msg)

        orders.update_one({"_id": pending["_id"]}, {"$set": {"status": "waiting_admin", "user_email": email}})

        bot.reply_to(message, "✅ Email đã gửi cho admin.\nAdmin sẽ xử lý và giao tài khoản sớm!")
        return

# ================== LỆNH ADMIN /giao (ĐÃ SỬA) ==================
@bot.message_handler(commands=['giao'])
def admin_giao_tai_khoan(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")

    try:
        order_code = int(message.text.split()[1])
        order = orders.find_one({"order_code": order_code, "status": {"$in": ["waiting_admin", "pending"]}})

        if not order:
            return bot.reply_to(message, "❌ Không tìm thấy đơn chờ xử lý!")

        category = order.get("category")
        user_id = order["user_id"]

        stock_doc = stocks.find_one({"category": category})
        if not stock_doc or not stock_doc.get("accounts"):
            return bot.reply_to(message, "❌ Hết stock!")

        account = stock_doc["accounts"].pop(0)
        stocks.update_one({"category": category}, {"$set": {"accounts": stock_doc["accounts"]}})

        bot.send_message(user_id, f"🎉 **Tài khoản đã được giao!**\nĐơn: #{order_code}\nTài khoản: {account}")

        orders.update_one({"order_code": order_code}, {"$set": {"status": "delivered", "delivered_at": datetime.now(), "account": account}})

        bot.reply_to(message, f"✅ Đã giao thành công đơn #{order_code}")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}\nSử dụng: /giao <mã đơn>")

# ================== FLASK + POLLING ==================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)
    print("🤖 Bot đang chạy...")
    bot.infinity_polling()
