import telebot
import random
import os
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from payos import PayOS
from payos.types import CreatePaymentLinkRequest
from flask import Flask, request, jsonify
import re
import json

load_dotenv()

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

WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://banhangtelegram01.onrender.com/webhook/payos')

CATEGORIES = {
    "hotspot": {"name": "Hotspot Shield 7D", "price": 2000, "type": "normal"},
    "gemini": {"name": "Gemini Pro 1 Acc 26-29D", "price": 40000, "type": "normal"},
    "capcut": {"name": "CapCut Pro 1 Tuần", "price": 2000, "type": "normal"},
    "canva1slot": {"name": "Canva 1 Slot", "price": 2000, "type": "canva_1slot"},
    "canva100slot": {"name": "Canva 100 Slot", "price": 30000, "type": "normal"},
    "youtube1slot": {"name": "YouTube 1 Slot", "price": 2000, "type": "youtube_1slot"},
}

for code, info in CATEGORIES.items():
    categories.update_one({"code": code}, {"$setOnInsert": {
        "code": code, "name": info["name"], "price": info["price"], "type": info.get("type"), "enabled": True
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

def notify_admin(order):
    user = get_user(order["user_id"])
    cat_name = CATEGORIES.get(order.get("category"), {}).get("name", "Nạp tiền")
    if order["type"] == "deposit":
        text = f"""
💰 **ĐƠN NẠP TIỀN MỚI**
Mã đơn: #{order['order_code']}
User ID: `{order['user_id']}`
Tên: {user.get('first_name', 'Không tên')}
Số tiền: **{order['amount']:,}đ**
        """
    else:
        text = f"""
🛒 **ĐƠN MUA HÀNG MỚI**
Mã đơn: #{order['order_code']}
User ID: `{order['user_id']}`
Tên: {user.get('first_name', 'Không tên')}
Sản phẩm: {cat_name}
Số tiền: **{order['amount']:,}đ**
        """
    try:
        bot.send_message(ADMIN_ID, text, parse_mode='Markdown')
    except:
        pass

# ================== ADMIN COMMANDS ==================
@bot.message_handler(commands=['users', 'balance'])
def admin_view_balances(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    all_users = users.find().sort("balance", -1)
    text = "📊 **DANH SÁCH SỐ DƯ USER**\n\n"
    for u in all_users:
        name = u.get('first_name') or u.get('username') or 'Unknown'
        text += f"👤 {name} (ID: `{u['user_id']}`) → 💰 `{u.get('balance', 0):,}đ`\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['duyetnap'])
def admin_duyet_nap(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        order_code = int(message.text.split()[1])
        order = orders.find_one({"order_code": order_code, "type": "deposit", "status": "pending"})
        if not order:
            return bot.reply_to(message, "❌ Không tìm thấy đơn nạp pending!")
        user_id = order['user_id']
        amount = order['amount']
        update_balance(user_id, amount)
        orders.update_one({"order_code": order_code}, {"$set": {"status": "approved", "approved_at": datetime.now()}})
        bot.send_message(user_id, f"✅ Nạp tiền đã được duyệt!\nSố tiền: +{amount:,}đ")
        bot.reply_to(message, f"✅ Đã duyệt nạp tiền #{order_code}")
    except:
        bot.reply_to(message, "Sử dụng: /duyetnap <mã đơn>")

@bot.message_handler(commands=['donnap'])
def admin_view_deposit_orders(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    pending_orders = orders.find({"type": "deposit", "status": "pending"}).sort("created_at", -1)
    text = "📋 **ĐƠN NẠP ĐANG CHỜ**\n\n"
    count = 0
    for order in pending_orders:
        text += f"🔹 #{order['order_code']} - {order['amount']:,}đ\n"
        count += 1
    if count == 0:
        text = "✅ Không có đơn nạp nào đang chờ!"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['giao'])
def admin_giao(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        order_code = int(message.text.split()[1])
        order = orders.find_one({"order_code": order_code})
        if not order:
            return bot.reply_to(message, "❌ Không tìm thấy đơn!")
        if order.get("status") != "paid":
            return bot.reply_to(message, "❌ Đơn hàng chưa được thanh toán!")
        category = order.get("category")
        user_id = order["user_id"]
        stock_doc = stocks.find_one({"category": category})
        if not stock_doc or not stock_doc.get("accounts"):
            return bot.reply_to(message, "❌ Hết stock loại này!")
        account = stock_doc["accounts"].pop(0)
        stocks.update_one({"category": category}, {"$set": {"accounts": stock_doc["accounts"]}})
        bot.send_message(user_id, f"""
🎉 **Tài khoản đã được giao!**
Đơn: #{order_code}
Sản phẩm: {CATEGORIES.get(category, {}).get('name', category)}
Tài khoản: {account}
        """)
        orders.update_one({"order_code": order_code}, {"$set": {"status": "delivered", "delivered_at": datetime.now(), "account": account}})
        bot.reply_to(message, f"✅ Đã giao thành công đơn #{order_code}")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['resetbalance'])
def admin_reset_balance(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        user_id = int(message.text.split()[1])
        old = get_user(user_id)['balance']
        update_balance(user_id, -old)
        bot.reply_to(message, f"✅ Đã reset số dư user `{user_id}`")
    except:
        bot.reply_to(message, "Sử dụng: /resetbalance <user_id>")

@bot.message_handler(commands=['resetallbalance'])
def admin_reset_all_balance(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    users.update_many({}, {"$set": {"balance": 0}})
    bot.reply_to(message, "✅ Đã reset số dư về 0 cho tất cả user.")

@bot.message_handler(commands=['resetcanva1'])
def admin_reset_canva1(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    stocks.update_one({"category": "canva1slot"}, {"$set": {"accounts": ["Slot sẵn sàng"] * 100}}, upsert=True)
    bot.reply_to(message, "✅ Đã reset Canva 1 Slot về **100 slot**!")

@bot.message_handler(commands=['resetyoutube'])
def admin_reset_youtube(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    stocks.update_one({"category": "youtube1slot"}, {"$set": {"accounts": ["Slot sẵn sàng"] * 10}}, upsert=True)
    bot.reply_to(message, "✅ Đã reset YouTube 1 Slot về **10 slot**!")

@bot.message_handler(commands=['setwebhook'])
def admin_set_webhook(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    bot.reply_to(message, f"""
🔧 **CẬP NHẬT WEBHOOK PAYOS**

URL Webhook: `{WEBHOOK_URL}`

📌 Đăng nhập [PayOS Dashboard](https://payos.vn/dashboard) → Cài đặt → Webhook → Dán URL trên → Lưu
    """, parse_mode='Markdown', disable_web_page_preview=True)

# ================== /start ==================
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
                f"{info['name']} - 🔒 Hết hàng", callback_data="outofstock"
            ))
    markup.add(telebot.types.InlineKeyboardButton("💰 Ví của tôi", callback_data="my_wallet"))
    markup.add(telebot.types.InlineKeyboardButton("💳 Nạp tiền vào ví", callback_data="deposit"))
    bot.send_message(message.chat.id, 
        f"👋 Chào **{message.from_user.first_name}**!\n\nChọn sản phẩm bạn muốn mua:", 
        parse_mode='Markdown', reply_markup=markup)

# ================== CALLBACK HANDLER ==================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    try:
        if call.data == "my_wallet":
            show_wallet(call)
        elif call.data == "deposit":
            deposit_menu(call)
        elif call.data.startswith("deposit_"):
            handle_deposit_amount(call)
        elif call.data.startswith("buy_"):
            handle_buy(call)
        elif call.data == "outofstock":
            bot.send_message(call.message.chat.id, "❌ Sản phẩm hiện đang hết hàng!")
    except Exception as e:
        print("Lỗi callback:", e)

def show_wallet(call):
    user = get_user(call.from_user.id)
    text = f"""
💰 **Ví của bạn:** `{user.get('balance', 0):,}đ`
    """
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

def deposit_menu(call):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("20.000đ", callback_data="deposit_20000"))
    markup.add(telebot.types.InlineKeyboardButton("50.000đ", callback_data="deposit_50000"))
    markup.add(telebot.types.InlineKeyboardButton("100.000đ", callback_data="deposit_100000"))
    markup.add(telebot.types.InlineKeyboardButton("200.000đ", callback_data="deposit_200000"))
    markup.add(telebot.types.InlineKeyboardButton("500.000đ", callback_data="deposit_500000"))
    markup.add(telebot.types.InlineKeyboardButton("Nhập số khác", callback_data="deposit_custom"))
    bot.send_message(call.message.chat.id, "💳 Chọn số tiền muốn nạp:", reply_markup=markup)

def handle_deposit_amount(call):
    if call.data == "deposit_custom":
        bot.send_message(call.message.chat.id, "Nhập số tiền muốn nạp (tối thiểu 10.000đ):")
        bot.register_next_step_handler(call.message, process_custom_deposit)
        return
    try:
        amount = int(call.data.split("_")[1])
        create_deposit_payment(call.message.chat.id, call.from_user.id, amount)
    except:
        bot.send_message(call.message.chat.id, "❌ Có lỗi khi xử lý.")

def process_custom_deposit(message):
    try:
        amount = int(message.text.strip())
        if amount < 10000:
            return bot.reply_to(message, "❌ Số tiền tối thiểu là 10.000đ!")
        create_deposit_payment(message.chat.id, message.from_user.id, amount)
    except ValueError:
        bot.reply_to(message, "❌ Vui lòng nhập số tiền hợp lệ!")

def create_deposit_payment(chat_id, user_id, amount):
    order_code = generate_order_code()
    order = {
        "order_code": order_code,
        "user_id": user_id,
        "type": "deposit",
        "amount": amount,
        "status": "pending",
        "created_at": datetime.now()
    }
    orders.insert_one(order)
    notify_admin(order)

    payment_data = CreatePaymentLinkRequest(
        order_code=order_code,
        amount=amount,
        description=f"Nap tien #{order_code}",
        return_url=f"https://t.me/{bot.get_me().username}",
        cancel_url=f"https://t.me/{bot.get_me().username}"
    )
    payment_link = payos.payment_requests.create(payment_data)

    bot.send_message(chat_id, f"""
💰 **Nạp tiền vào ví**
Mã đơn: #{order_code}
Số tiền: **{amount:,}đ**
🔗 [Thanh toán ngay]({payment_link.checkout_url})
    """, parse_mode='Markdown')

# ================== MUA HÀNG ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    code = call.data.split("_")[1]
    info = CATEGORIES.get(code)
    if not info: return

    user = get_user(call.from_user.id)
    price = info["price"]
    stock_count = get_stock_count(code)

    if stock_count <= 0:
        return bot.send_message(call.message.chat.id, "❌ Sản phẩm đã hết hàng!")

    if user.get("balance", 0) >= price:
        update_balance(call.from_user.id, -price)
        stock_doc = stocks.find_one({"category": code})
        if stock_doc and stock_doc.get("accounts"):
            account = stock_doc["accounts"].pop(0)
            stocks.update_one({"category": code}, {"$set": {"accounts": stock_doc["accounts"]}})
            bot.send_message(call.message.chat.id, f"""
🎉 **Mua thành công!**
Sản phẩm: {info['name']}
Tài khoản: {account}
            """)
    else:
        order_code = generate_order_code()
        order = {
            "order_code": order_code, 
            "user_id": call.from_user.id, 
            "category": code, 
            "amount": price, 
            "type": "purchase", 
            "status": "pending", 
            "created_at": datetime.now()
        }
        orders.insert_one(order)
        notify_admin(order)

        payment_data = CreatePaymentLinkRequest(
            order_code=order_code,
            amount=price,
            description=f"Mua {info['name'][:20]} #{order_code}",
            return_url=f"https://t.me/{bot.get_me().username}",
            cancel_url=f"https://t.me/{bot.get_me().username}"
        )
        payment_link = payos.payment_requests.create(payment_data)
        bot.send_message(call.message.chat.id, f"""
✅ Đơn hàng #{order_code} đã tạo!
🔗 [Thanh toán ngay]({payment_link.checkout_url})
        """, parse_mode='Markdown')

# ================== FLASK WEBHOOK ==================
flask_app = Flask(__name__)

def process_payment_success(data):
    try:
        order_code = data.get('orderCode')
        amount = data.get('amount')
        
        order = orders.find_one({"order_code": order_code})
        if not order:
            print(f"Không tìm thấy đơn #{order_code}")
            return False
        
        if order.get("status") in ["approved", "paid"]:
            print(f"Đơn #{order_code} đã xử lý rồi")
            return True
        
        user_id = order["user_id"]
        
        if order["type"] == "deposit":
            update_balance(user_id, amount)
            orders.update_one({"order_code": order_code}, {"$set": {
                "status": "approved", 
                "approved_at": datetime.now()
            }})
            bot.send_message(user_id, f"✅ Nạp tiền thành công! +{amount:,}đ")
            print(f"✅ Đã nạp {amount}đ cho user {user_id}")
        elif order["type"] == "purchase":
            orders.update_one({"order_code": order_code}, {"$set": {
                "status": "paid", 
                "paid_at": datetime.now()
            }})
            bot.send_message(user_id, f"✅ Thanh toán thành công! Đơn hàng đang được xử lý.")
            print(f"✅ Đã thanh toán đơn #{order_code}")
        return True
    except Exception as e:
        print(f"Lỗi: {e}")
        return False

@flask_app.route('/webhook/payos', methods=['POST'])
def payos_webhook():
    print(f"📨 Nhận webhook PayOS: {request.get_json()}")
    try:
        data = request.get_json()
        if data and data.get('status') == 'PAID':
            success = process_payment_success(data)
            return jsonify({"success": success}), 200 if success else 500
        return jsonify({"success": True}), 200
    except Exception as e:
        print(f"Lỗi: {e}")
        return jsonify({"error": str(e)}), 500

# ========== TELEGRAM WEBHOOK ENDPOINT - QUAN TRỌNG ==========
@flask_app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    """Endpoint nhận update từ Telegram"""
    try:
        # Đọc dữ liệu JSON từ request
        json_str = request.get_data().decode('utf-8')
        update_dict = json.loads(json_str)
        
        # Chuyển đổi thành Update object và xử lý
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        
        print(f"✅ Đã xử lý telegram update: {update.update_id}")
        return jsonify({"ok": True}), 200
    except Exception as e:
        print(f"❌ Lỗi telegram webhook: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@flask_app.route('/webhook/telegram', methods=['GET'])
def telegram_webhook_get():
    """GET request cho webhook (dùng để test)"""
    return jsonify({"status": "Telegram webhook endpoint is ready"}), 200

@flask_app.route('/')
def home():
    return jsonify({"status": "Bot is running!", "time": datetime.now().isoformat()})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app_url = f"https://banhangtelegram01.onrender.com"
    telegram_webhook_url = f"{app_url}/webhook/telegram"
    
    # Set webhook cho Telegram bot
    try:
        bot.remove_webhook()
        result = bot.set_webhook(url=telegram_webhook_url)
        if result:
            print(f"✅ Telegram webhook set thành công: {telegram_webhook_url}")
        else:
            print(f"❌ Set webhook thất bại")
    except Exception as e:
        print(f"❌ Lỗi set webhook: {e}")
    
    print(f"🤖 Bot đang chạy với webhook mode!")
    print(f"📡 Telegram Webhook URL: {telegram_webhook_url}")
    print(f"💳 PayOS Webhook URL: {app_url}/webhook/payos")
    
    flask_app.run(host="0.0.0.0", port=port, debug=False)
