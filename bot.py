import telebot
import random
import os
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from payos import PayOS
from payos.types import CreatePaymentLinkRequest
from flask import Flask
import threading
import time
import re

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

RATE_USDT_VND = 26150  # Tỷ giá USDT → VND

CATEGORIES = {
    "hotspot": {"name_vi": "Hotspot Shield 7D", "name_en": "Hotspot Shield 7D", "price": 2000, "type": "normal"},
    "gemini": {"name_vi": "Gemini Pro 1 Acc 26-29D", "name_en": "Gemini Pro 1 Acc 26-29D", "price": 40000, "type": "normal"},
    "capcut": {"name_vi": "CapCut Pro 1 Tuần", "name_en": "CapCut Pro 1 Week", "price": 2000, "type": "normal"},
    "canva1slot": {"name_vi": "Canva 1 Slot", "name_en": "Canva 1 Slot", "price": 2000, "type": "canva_1slot"},
    "canva100slot": {"name_vi": "Canva 100 Slot", "name_en": "Canva 100 Slot", "price": 30000, "type": "normal"},
    "youtube1slot": {"name_vi": "YouTube 1 Slot", "name_en": "YouTube 1 Slot", "price": 2000, "type": "youtube_1slot"},
}

for code, info in CATEGORIES.items():
    categories.update_one({"code": code}, {"$setOnInsert": {
        "code": code, 
        "name_vi": info["name_vi"], 
        "name_en": info["name_en"], 
        "price": info["price"], 
        "type": info.get("type", "normal"), 
        "enabled": True
    }}, upsert=True)

# ================== TRANSLATIONS ==================
TRANSLATIONS = {
    "vi": {
        "choose_lang": "🌐 Chọn ngôn ngữ / Choose language:",
        "welcome": "👋 Chào **{name}**!\n\nChọn sản phẩm bạn muốn mua:",
        "my_wallet": "💰 Ví của tôi",
        "deposit": "💳 Nạp tiền vào ví",
        "change_lang": "🌐 Đổi ngôn ngữ",
        "out_of_stock": "🔒 Hết hàng",
        "buy_btn": "🛒 Mua {name} - {price:,}đ (còn {stock})",
        "deposit_menu": "💳 Chọn số tiền muốn nạp:",
        "deposit_custom": "Nhập số khác",
        "deposit_binance": "💱 Nạp qua Binance USDT (min 1 USDT)",
        "custom_prompt": "Nhập số tiền muốn nạp (tối thiểu 2.000đ):",
        "binance_prompt": "Nhập số USDT muốn nạp (tối thiểu 1 USDT):",
        "min_deposit": "❌ Số tiền tối thiểu là 2.000đ!",
        "min_usdt": "❌ Số USDT tối thiểu là 1 USDT!",
        "invalid_amount": "❌ Vui lòng nhập số tiền hợp lệ!",
        "deposit_payos": "💰 **Nạp tiền vào ví**\n\nMã đơn: #{order_code}\nSố tiền: **{amount:,}đ**\n\n🔗 [Thanh toán ngay]({url})",
        "binance_deposit_msg": """💱 **Nạp qua Binance USDT**

Mã đơn: #{order_code}
Số USDT: **{usdt} USDT** (~{vnd:,}đ)

🔸 Chuyển chính xác **{usdt} USDT** đến Binance UID: **1163285604**
🔸 Ghi chú (Memo): **#{order_code}** (rất quan trọng!)

Sau khi chuyển xong, admin sẽ duyệt và cộng tiền vào ví.""",
        "no_stock": "❌ Sản phẩm đã hết hàng!",
        "not_exist": "❌ Sản phẩm không tồn tại!",
        "insufficient": "❌ Số dư ví không đủ!\nCần {price:,}đ\nHiện có: {balance:,}đ\nVui lòng nạp trước.",
        "email_prompt": "✅ Đã trừ {price:,}đ từ ví!\n\n📧 Vui lòng gửi **email (@gmail.com)** của bạn ngay bây giờ.",
        "email_invalid": "❌ Chỉ chấp nhận email @gmail.com!",
        "email_sent": "✅ Email đã được gửi cho admin!",
        "buy_success": """🎉 **Mua thành công từ ví!**

Sản phẩm: {name}
Tài khoản: {account}
Số dư còn lại: {balance:,}đ""",
        "purchase_pending": """✅ Đơn hàng #{order_code} đã tạo!

💰 Số tiền: {price:,}đ
📦 Sản phẩm: {name}

🔗 [Thanh toán ngay]({url})""",
    },
    "en": {
        "choose_lang": "🌐 Choose language:",
        "welcome": "👋 Hello **{name}**!\n\nChoose the product you want to buy:",
        "my_wallet": "💰 My Wallet",
        "deposit": "💳 Deposit to wallet",
        "change_lang": "🌐 Change language",
        "out_of_stock": "🔒 Out of stock",
        "buy_btn": "🛒 Buy {name} - {usdt:.2f} USDT ({stock} left)",
        "deposit_menu": "💳 Select deposit amount:",
        "deposit_custom": "Custom amount",
        "deposit_binance": "💱 Deposit via Binance USDT (min 1 USDT)",
        "custom_prompt": "Enter deposit amount (minimum 2,000đ):",
        "binance_prompt": "Enter USDT amount to deposit (minimum 1 USDT):",
        "min_deposit": "❌ Minimum deposit is 2,000đ!",
        "min_usdt": "❌ Minimum is 1 USDT!",
        "invalid_amount": "❌ Please enter a valid amount!",
        "deposit_payos": "💰 **Deposit to wallet**\n\nOrder: #{order_code}\nAmount: **{amount:,}đ**\n\n🔗 [Pay Now]({url})",
        "binance_deposit_msg": """💱 **Deposit via Binance USDT**

Order: #{order_code}
USDT: **{usdt} USDT** (~{vnd:,}đ)

🔸 Send exactly **{usdt} USDT** to Binance UID: **1163285604**
🔸 Memo/Note: **#{order_code}** (very important!)

After transfer, admin will approve and add to your wallet.""",
        "no_stock": "❌ Product is out of stock!",
        "not_exist": "❌ Product does not exist!",
        "insufficient": "❌ Insufficient balance!\nRequired: {price:,}đ\nCurrent: {balance:,}đ\nPlease deposit first.",
        "email_prompt": "✅ Deducted {price:,}đ from wallet!\n\n📧 Please send your **email (@gmail.com)** now.",
        "email_invalid": "❌ Only @gmail.com emails are accepted!",
        "email_sent": "✅ Email has been sent to admin!",
        "buy_success": """🎉 **Purchase successful from wallet!**

Product: {name}
Account: {account}
Remaining balance: {balance:,}đ""",
        "purchase_pending": """✅ Order #{order_code} created!

💰 Amount: {price:,}đ
📦 Product: {name}

🔗 [Pay Now]({url})""",
    }
}

def get_text(user_id, key, **kwargs):
    user = get_user(user_id)
    lang = user.get("language", "vi")
    text = TRANSLATIONS.get(lang, TRANSLATIONS["vi"]).get(key, key)
    try:
        return text.format(**kwargs)
    except:
        return text

def vnd_to_usdt(vnd):
    return round(vnd / RATE_USDT_VND, 2)

def get_user(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "first_name": None,
            "balance": 0,
            "joined_at": datetime.now(),
            "language": "vi"
        }
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
    try:
        user = get_user(order["user_id"])
        cat_name = CATEGORIES.get(order.get("category", ""), {}).get("name_vi", "Nạp tiền")
        text = f"""
🛒 **ĐƠN MỚI**
Mã đơn: #{order.get('order_code')}
User ID: `{order['user_id']}`
Tên: {user.get('first_name', 'Không tên')}
Sản phẩm: {cat_name}
Số tiền: **{order.get('amount', 0):,}đ**
Trạng thái: Chờ xử lý
        """
        bot.send_message(ADMIN_ID, text)
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
        order = orders.find_one({"order_code": order_code, "status": "pending"})
        if not order:
            return bot.reply_to(message, "❌ Không tìm thấy đơn nạp pending!")
        amount = order['amount']
        update_balance(order['user_id'], amount)
        orders.update_one({"order_code": order_code}, {"$set": {"status": "approved", "approved_at": datetime.now()}})
        bot.send_message(order['user_id'], f"✅ Nạp tiền đã được duyệt!\nSố tiền: +{amount:,}đ\nSố dư hiện tại: {get_user(order['user_id'])['balance']:,}đ")
        bot.reply_to(message, f"✅ Đã duyệt nạp tiền #{order_code}")
    except:
        bot.reply_to(message, "Sử dụng: /duyetnap <mã đơn>")

@bot.message_handler(commands=['giao'])
def admin_giao(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        order_code = int(message.text.split()[1])
        order = orders.find_one({"order_code": order_code})
        if not order or not order.get("category"):
            return bot.reply_to(message, "❌ Không tìm thấy đơn!")
        category = order["category"]
        stock_doc = stocks.find_one({"category": category})
        if not stock_doc or not stock_doc.get("accounts"):
            return bot.reply_to(message, "❌ Hết stock loại này!")
        account = stock_doc["accounts"].pop(0)
        stocks.update_one({"category": category}, {"$set": {"accounts": stock_doc["accounts"]}})
        bot.send_message(order["user_id"], f"""
🎉 **Tài khoản đã được giao!**

Đơn: #{order_code}
Sản phẩm: {CATEGORIES.get(category, {}).get('name_vi', category)}
Tài khoản: {account}
        """)
        orders.update_one({"order_code": order_code}, {"$set": {"status": "delivered", "delivered_at": datetime.now(), "account": account}})
        bot.reply_to(message, f"✅ Đã giao thành công đơn #{order_code}")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}\nSử dụng: /giao <mã đơn>")

@bot.message_handler(commands=['resetbalance'])
def admin_reset_balance(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        user_id = int(message.text.split()[1])
        old = get_user(user_id)['balance']
        update_balance(user_id, -old)
        bot.reply_to(message, f"✅ Đã reset số dư user `{user_id}` từ {old:,}đ → 0đ")
    except:
        bot.reply_to(message, "Sử dụng: /resetbalance <user_id>")

@bot.message_handler(commands=['resetallbalance'])
def admin_reset_all_balance(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
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

# ================== /start ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="set_lang_vi"))
    markup.add(telebot.types.InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en"))
    bot.send_message(message.chat.id, TRANSLATIONS["vi"]["choose_lang"], reply_markup=markup)

# ================== CALLBACK HANDLER ==================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id

    if call.data.startswith("set_lang_"):
        lang = "vi" if call.data == "set_lang_vi" else "en"
        users.update_one({"user_id": user_id}, {"$set": {"language": lang}})
        msg = "✅ Ngôn ngữ đã được đặt thành Tiếng Việt!" if lang == "vi" else "✅ Language has been set to English!"
        bot.send_message(call.message.chat.id, msg)
        show_main_menu(call.message.chat.id, user_id)
        return

    if call.data == "my_wallet":
        show_wallet(call)
    elif call.data == "deposit":
        deposit_menu(call)
    elif call.data.startswith("deposit_"):
        handle_deposit_amount(call)
    elif call.data.startswith("buy_"):
        handle_buy(call)
    elif call.data == "outofstock":
        bot.send_message(call.message.chat.id, get_text(call.from_user.id, "no_stock"))
    elif call.data == "change_language":
        start(call.message)
    elif call.data in ["confirm_reset_all", "cancel_reset_all"]:
        handle_reset_all(call)

def show_main_menu(chat_id, user_id):
    user = get_user(user_id)
    lang = user.get("language", "vi")
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)

    for code, info in CATEGORIES.items():
        stock = get_stock_count(code)
        price_vnd = info["price"]
        if lang == "vi":
            name = info["name_vi"]
            btn_text = get_text(user_id, "buy_btn", name=name, price=price_vnd, stock=stock) if stock > 0 else f"{name} - {get_text(user_id, 'out_of_stock')}"
        else:
            name = info["name_en"]
            price_usdt = vnd_to_usdt(price_vnd)
            btn_text = f"🛒 Buy {name} - {price_usdt:.2f} USDT ({stock} left)" if stock > 0 else f"{name} - {get_text(user_id, 'out_of_stock')}"
        markup.add(telebot.types.InlineKeyboardButton(btn_text, callback_data=f"buy_{code}" if stock > 0 else "outofstock"))

    markup.add(telebot.types.InlineKeyboardButton(get_text(user_id, "my_wallet"), callback_data="my_wallet"))
    markup.add(telebot.types.InlineKeyboardButton(get_text(user_id, "deposit"), callback_data="deposit"))
    markup.add(telebot.types.InlineKeyboardButton(get_text(user_id, "change_lang"), callback_data="change_language"))

    welcome = get_text(user_id, "welcome", name=call.from_user.first_name or "User")
    bot.send_message(chat_id, welcome, parse_mode='Markdown', reply_markup=markup)

def show_wallet(call):
    user = get_user(call.from_user.id)
    text = f"""
🆔 **ID:** `{call.from_user.id}`
👤 **Tên:** {call.from_user.first_name or 'Không tên'}
💰 **Số dư:** `{user.get('balance', 0):,}đ`
    """
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

# ================== NẠP TIỀN ==================
def deposit_menu(call):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("50.000đ", callback_data="deposit_50000"))
    markup.add(telebot.types.InlineKeyboardButton("100.000đ", callback_data="deposit_100000"))
    markup.add(telebot.types.InlineKeyboardButton("200.000đ", callback_data="deposit_200000"))
    markup.add(telebot.types.InlineKeyboardButton(get_text(call.from_user.id, "deposit_custom"), callback_data="deposit_custom"))
    markup.add(telebot.types.InlineKeyboardButton(get_text(call.from_user.id, "deposit_binance"), callback_data="deposit_binance"))
    bot.send_message(call.message.chat.id, get_text(call.from_user.id, "deposit_menu"), reply_markup=markup)

def handle_deposit_amount(call):
    if call.data == "deposit_custom":
        bot.send_message(call.message.chat.id, get_text(call.from_user.id, "custom_prompt"))
        bot.register_next_step_handler(call.message, process_custom_deposit)
        return
    elif call.data == "deposit_binance":
        bot.send_message(call.message.chat.id, get_text(call.from_user.id, "binance_prompt"))
        bot.register_next_step_handler(call.message, process_binance_deposit)
        return
    try:
        amount = int(call.data.split("_")[1])
        create_payos_deposit(call.message.chat.id, call.from_user.id, amount)
    except:
        bot.send_message(call.message.chat.id, "❌ Có lỗi khi xử lý.")

def process_custom_deposit(message):
    try:
        amount = int(message.text.strip())
        if amount < 2000:
            return bot.reply_to(message, get_text(message.from_user.id, "min_deposit"))
        create_payos_deposit(message.chat.id, message.from_user.id, amount)
    except:
        bot.reply_to(message, get_text(message.from_user.id, "invalid_amount"))

def process_binance_deposit(message):
    try:
        usdt = float(message.text.strip().replace(",", "."))
        if usdt < 1:
            return bot.reply_to(message, get_text(message.from_user.id, "min_usdt"))
        vnd = int(usdt * RATE_USDT_VND)
        create_binance_deposit(message.chat.id, message.from_user.id, usdt, vnd)
    except:
        bot.reply_to(message, get_text(message.from_user.id, "invalid_amount"))

def create_payos_deposit(chat_id, user_id, amount):
    order_code = generate_order_code()
    orders.insert_one({"order_code": order_code, "user_id": user_id, "type": "deposit", "amount": amount, "status": "pending", "created_at": datetime.now()})
    notify_admin({"order_code": order_code, "user_id": user_id, "type": "deposit", "amount": amount})
    payment_data = CreatePaymentLinkRequest(
        order_code=order_code, amount=amount, description=f"Nap #{order_code}",
        return_url="https://t.me/" + bot.get_me().username,
        cancel_url="https://t.me/" + bot.get_me().username
    )
    payment_link = payos.payment_requests.create(payment_data)
    text = get_text(user_id, "deposit_payos", order_code=order_code, amount=amount, url=payment_link.checkout_url)
    bot.send_message(chat_id, text, parse_mode='Markdown')

def create_binance_deposit(chat_id, user_id, usdt, vnd):
    order_code = generate_order_code()
    orders.insert_one({"order_code": order_code, "user_id": user_id, "type": "deposit_binance", "amount": vnd, "amount_usdt": usdt, "status": "pending", "created_at": datetime.now()})
    notify_admin({"order_code": order_code, "user_id": user_id, "type": "deposit_binance", "amount": vnd})
    text = get_text(user_id, "binance_deposit_msg", order_code=order_code, usdt=usdt, vnd=vnd)
    bot.send_message(chat_id, text, parse_mode='Markdown')

# ================== MUA HÀNG ==================
def handle_buy(call):
    code = call.data.split("_")[1]
    info = CATEGORIES.get(code)
    if not info:
        return bot.send_message(call.message.chat.id, get_text(call.from_user.id, "not_exist"))

    user = get_user(call.from_user.id)
    price = info["price"]
    stock_count = get_stock_count(code)

    if stock_count <= 0:
        return bot.send_message(call.message.chat.id, get_text(call.from_user.id, "no_stock"))

    if user.get("balance", 0) < price:
        return bot.send_message(call.message.chat.id, get_text(call.from_user.id, "insufficient", price=price, balance=user.get('balance', 0)))

    update_balance(call.from_user.id, -price)

    if code in ["canva1slot", "youtube1slot"]:
        order_code = generate_order_code()
        orders.insert_one({
            "order_code": order_code,
            "user_id": call.from_user.id,
            "category": code,
            "amount": price,
            "type": code,
            "status": "waiting_email",
            "created_at": datetime.now()
        })
        notify_admin({"order_code": order_code, "user_id": call.from_user.id, "category": code, "amount": price})
        stock_doc = stocks.find_one({"category": code})
        if stock_doc and stock_doc.get("accounts"):
            stock_doc["accounts"].pop(0)
            stocks.update_one({"category": code}, {"$set": {"accounts": stock_doc["accounts"]}})
        bot.send_message(call.message.chat.id, get_text(call.from_user.id, "email_prompt", price=price))
    else:
        # Sản phẩm thường - giao ngay
        stock_doc = stocks.find_one({"category": code})
        if stock_doc and stock_doc.get("accounts"):
            account = stock_doc["accounts"].pop(0)
            stocks.update_one({"category": code}, {"$set": {"accounts": stock_doc["accounts"]}})
            bot.send_message(call.message.chat.id, get_text(call.from_user.id, "buy_success", 
                name=info.get("name_vi" if user.get("language") == "vi" else "name_en"), 
                account=account, 
                balance=get_user(call.from_user.id)['balance']))

# ================== XỬ LÝ EMAIL ==================
@bot.message_handler(func=lambda m: True)
def handle_user_message(message):
    pending = orders.find_one({"user_id": message.from_user.id, "status": "waiting_email"})
    if pending:
        email = message.text.strip()
        if not re.match(r'^[\w\.-]+@gmail\.com$', email, re.IGNORECASE):
            return bot.reply_to(message, get_text(message.from_user.id, "email_invalid"))
        bot.send_message(ADMIN_ID, f"""
📨 **YÊU CẦU EMAIL**
Mã đơn: #{pending['order_code']}
User ID: `{message.from_user.id}`
Email: `{email}`
Sản phẩm: {CATEGORIES.get(pending.get('category'), {}).get('name_vi')}
        """)
        orders.update_one({"_id": pending["_id"]}, {"$set": {"status": "waiting_admin", "user_email": email}})
        bot.reply_to(message, get_text(message.from_user.id, "email_sent"))
        return

# ================== FLASK + POLLING ==================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)
    print("🤖 Bot đang chạy hoàn chỉnh - Hỗ trợ 2 ngôn ngữ + Nạp Binance USDT!")
    bot.infinity_polling()
