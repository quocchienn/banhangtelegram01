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
users = db['users']          # user + số dư ví
orders = db['orders']        # đơn hàng
stocks = db['stocks']        # stock tài khoản
categories = db['categories']

# Categories
CATEGORIES = {
    "hotspot": {"name": "Hotspot Shield 7D", "price": 2000},
    "gemini": {"name": "Gemini Pro 1 Acc 26-29D", "price": 40000},
    "capcut": {"name": "CapCut Pro 1 Tuần", "price": 2000},
}

# Khởi tạo categories
for code, info in CATEGORIES.items():
    categories.update_one(
        {"code": code},
        {"$setOnInsert": {
            "code": code,
            "name": info["name"],
            "price": info["price"],
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
    users.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": amount}}
    )

def generate_order_code():
    return random.randint(10000000, 99999999)

def add_to_stock(category, accounts_list):
    stocks.update_one(
        {"category": category},
        {"$push": {"accounts": {"$each": accounts_list}}},
        upsert=True
    )

# ================== COMMANDS ==================
@bot.message_handler(commands=['start'])
def start(message):
    user = get_user(message.from_user.id)
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

    markup.add(telebot.types.InlineKeyboardButton("💰 Ví của tôi", callback_data="my_wallet"))
    markup.add(telebot.types.InlineKeyboardButton("💳 Nạp tiền vào ví", callback_data="deposit"))

    bot.send_message(message.chat.id, 
        f"👋 Chào **{message.from_user.first_name}**!\n\n"
        f"Chọn tài khoản Pro bạn muốn mua:", 
        parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(commands=['me', 'info'])
def show_info(message):
    user = get_user(message.from_user.id)
    joined = user.get('joined_at', datetime.now()).strftime('%d/%m/%Y')

    text = f"""
🆔 **ID:** `{message.from_user.id}`
👤 **Tên:** {message.from_user.first_name}
💰 **Số dư:** `{user.get('balance', 0):,}đ`
📅 **Tham gia:** {joined}
    """
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

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

# ================== NẠP TIỀN ==================
@bot.callback_query_handler(func=lambda call: call.data == "deposit")
def deposit_menu(call):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("50.000đ", callback_data="deposit_50000"))
    markup.add(telebot.types.InlineKeyboardButton("100.000đ", callback_data="deposit_100000"))
    markup.add(telebot.types.InlineKeyboardButton("200.000đ", callback_data="deposit_200000"))
    markup.add(telebot.types.InlineKeyboardButton("Nhập số khác", callback_data="deposit_custom"))

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "💳 Chọn số tiền muốn nạp vào ví:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("deposit_"))
def handle_deposit(call):
    bot.answer_callback_query(call.id)

    if call.data == "deposit_custom":
        bot.send_message(call.message.chat.id, "Nhập số tiền muốn nạp (ví dụ: 50000):")
        bot.register_next_step_handler(call.message, process_custom_deposit)
        return

    amount = int(call.data.split("_")[1])
    order_code = generate_order_code()

    orders.insert_one({
        "order_code": order_code,
        "user_id": call.from_user.id,
        "type": "deposit",
        "amount": amount,
        "status": "pending",
        "created_at": datetime.now()
    })

    payment_data = CreatePaymentLinkRequest(
        order_code=order_code,
        amount=amount,
        description=f"Nap vi {amount}đ",
        return_url="https://t.me/" + bot.get_me().username,
        cancel_url="https://t.me/" + bot.get_me().username
    )

    try:
        payment_link = payos.payment_requests.create(payment_data)
        bot.send_message(call.message.chat.id, 
            f"💰 **Nạp tiền vào ví**\n\n"
            f"Số tiền: {amount:,}đ\n"
            f"Mã đơn: #{order_code}\n\n"
            f"🔗 Thanh toán tại: {payment_link.checkout_url}", 
            parse_mode='Markdown')
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Lỗi tạo link nạp: {str(e)}")

def process_custom_deposit(message):
    try:
        amount = int(message.text.strip())
        if amount < 10000:
            return bot.reply_to(message, "Số tiền tối thiểu là 10.000đ!")

        order_code = generate_order_code()
        orders.insert_one({
            "order_code": order_code,
            "user_id": message.from_user.id,
            "type": "deposit",
            "amount": amount,
            "status": "pending",
            "created_at": datetime.now()
        })

        payment_data = CreatePaymentLinkRequest(
            order_code=order_code,
            amount=amount,
            description=f"Nap vi {amount}đ",
            return_url="https://t.me/" + bot.get_me().username,
            cancel_url="https://t.me/" + bot.get_me().username
        )
        payment_link = payos.payment_requests.create(payment_data)

        bot.send_message(message.chat.id, 
            f"💰 **Nạp tiền vào ví**\n\n"
            f"Số tiền: {amount:,}đ\n"
            f"Mã đơn: #{order_code}\n\n"
            f"🔗 Thanh toán tại: {payment_link.checkout_url}", 
            parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "Vui lòng nhập số tiền hợp lệ!")
    except Exception as e:
        bot.reply_to(message, f"Lỗi: {str(e)}")

# ================== MUA HÀNG (từ ví hoặc PayOS) ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    category = call.data.split("_")[1]
    info = CATEGORIES.get(category)
    if not info:
        return bot.answer_callback_query(call.id, "Sản phẩm không tồn tại!")

    user = get_user(call.from_user.id)
    price = info["price"]

    # Kiểm tra số dư ví
    if user.get("balance", 0) >= price:
        # Thanh toán từ ví
        update_balance(call.from_user.id, -price)

        # Lấy tài khoản từ stock
        stock_doc = stocks.find_one({"category": category})
        if stock_doc and stock_doc.get("accounts"):
            account = stock_doc["accounts"].pop(0)
            stocks.update_one({"category": category}, {"$set": {"accounts": stock_doc["accounts"]}})

            bot.send_message(call.from_user.id, f"""
🎉 **Mua thành công từ ví!**

Sản phẩm: {info['name']}
Tài khoản: {account}
Số dư còn lại: {user['balance'] - price:,}đ
            """)
        else:
            bot.send_message(call.from_user.id, "❌ Sản phẩm tạm hết hàng!")
    else:
        # Không đủ tiền → tạo link PayOS
        order_code = generate_order_code()
        orders.insert_one({
            "order_code": order_code,
            "user_id": call.from_user.id,
            "category": category,
            "amount": price,
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

# ================== FLASK + WEBHOOK ==================
flask_app = Flask(__name__)

@flask_app.route('/payos-webhook', methods=['POST'])
def payos_webhook():
    try:
        data = request.json
        webhook_data = payos.webhooks.verify(data)

        if webhook_data.success:
            order_code = webhook_data.data.get('orderCode')
            order = orders.find_one({"order_code": order_code})

            if order and order['status'] == 'pending':
                orders.update_one(
                    {"order_code": order_code},
                    {"$set": {"status": "paid", "paid_at": datetime.now()}}
                )

                user_id = order['user_id']
                amount = order['amount']

                if order.get('type') == 'deposit':
                    update_balance(user_id, amount)
                    bot.send_message(user_id, f"✅ **Nạp tiền thành công!**\nSố tiền: {amount:,}đ\nSố dư hiện tại: {get_user(user_id)['balance']:,}đ")
                # Có thể thêm xử lý mua hàng từ PayOS sau này

    except Exception as e:
        print("Webhook error:", str(e))

    return "OK", 200

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
