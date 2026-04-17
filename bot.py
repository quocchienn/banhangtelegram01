import telebot
import random
import os
from datetime import datetime, timedelta
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
ADMIN_BINANCE_ID = os.getenv('ADMIN_BINANCE_ID', '1163285604')
USDT_RATE = int(os.getenv('USDT_RATE', 27000))

users = db['users']
orders = db['orders']
stocks = db['stocks']
categories = db['categories']

# Collection để lưu trạng thái chờ upload
pending_uploads = db['pending_uploads']

# Biến toàn cục lưu broadcast đang chờ
pending_broadcast = None

CATEGORIES = {
    "hotspot": {"name": "Hotspot Shield 7D", "name_en": "Hotspot Shield 7D", "price": 2000, "price_usdt": 0.08, "type": "normal"},
    "gemini": {"name": "Gemini Pro 1 Acc 26-29D", "name_en": "Gemini Pro 1 Acc 26-29D", "price": 40000, "price_usdt": 1.6, "type": "normal"},
    "capcut": {"name": "CapCut Pro 1 Tuần", "name_en": "CapCut Pro 1 Week", "price": 2000, "price_usdt": 0.08, "type": "normal"},
    "canva1slot": {"name": "Canva 1 Slot", "name_en": "Canva 1 Slot", "price": 2000, "price_usdt": 0.08, "type": "canva_1slot"},
    "canva100slot": {"name": "Canva 100 Slot", "name_en": "Canva 100 Slot", "price": 30000, "price_usdt": 1.2, "type": "normal"},
    "youtube1slot": {"name": "YouTube 1 Slot", "name_en": "YouTube 1 Slot", "price": 2000, "price_usdt": 0.08, "type": "youtube_1slot"},
}

# Khởi tạo categories
for code, info in CATEGORIES.items():
    cat = categories.find_one({"code": code})
    if cat:
        # Cập nhật giá từ database vào CATEGORIES
        CATEGORIES[code]["price"] = cat.get("price", info["price"])
        CATEGORIES[code]["price_usdt"] = cat.get("price_usdt", info["price_usdt"])
    else:
        categories.insert_one({
            "code": code, "name": info["name"], "name_en": info["name_en"], 
            "price": info["price"], "price_usdt": info["price_usdt"], 
            "type": info.get("type"), "enabled": True
        })

# ================== LANGUAGE SYSTEM ==================
LANGUAGES = {
    "vi": {
        "welcome": "👋 Chào **{name}**!\n\nChọn sản phẩm bạn muốn mua:",
        "choose_lang": "🌐 **Chọn ngôn ngữ / Choose language**\n\nVui lòng chọn ngôn ngữ bạn muốn sử dụng.",
        "lang_vi": "🇻🇳 Tiếng Việt",
        "lang_en": "🇬🇧 English",
        "wallet": "💰 Ví của tôi",
        "deposit": "💳 Nạp tiền VND",
        "deposit_usdt": "💵 Nạp USDT qua Binance",
        "buy": "🛒 Mua {name} - {price}",
        "out_of_stock": "{name} - 🔒 Hết hàng",
        "insufficient": "❌ Số dư ví không đủ!\nCần {price:,}đ\nHiện có: {balance:,}đ",
        "insufficient_usdt": "❌ Số dư USDT không đủ!\nCần {price} USDT\nHiện có: {balance} USDT",
        "deposit_usdt_prompt": "💵 Nhập số USDT muốn nạp (tối thiểu 1 USDT):",
        "deposit_usdt_min": "❌ Số USDT tối thiểu là 1!",
        "deposit_usdt_invalid": "❌ Vui lòng nhập số hợp lệ!",
        "change_lang": "🌐 Đổi ngôn ngữ / Change Language",
        "back_to_menu": "🔙 Quay lại menu chính",
        "email_prompt": "📧 Vui lòng gửi **email (@gmail.com)** của bạn ngay bây giờ:",
        "email_sent": "✅ Email đã được gửi cho admin! Chúng tôi sẽ xử lý sớm.",
        "email_invalid": "❌ Chỉ chấp nhận email @gmail.com! Vui lòng nhập lại:",
        "reload_menu": "🔄 Tải lại / Reload",
    },
    "en": {
        "welcome": "👋 Hello **{name}**!\n\nChoose a product to buy:",
        "choose_lang": "🌐 **Choose language / Chọn ngôn ngữ**\n\nPlease choose your preferred language.",
        "lang_vi": "🇻🇳 Vietnamese",
        "lang_en": "🇬🇧 English",
        "wallet": "💰 My Wallet",
        "deposit": "💳 Deposit VND",
        "deposit_usdt": "💵 Deposit USDT via Binance",
        "buy": "🛒 Buy {name} - {price} USDT",
        "out_of_stock": "{name} - 🔒 Out of Stock",
        "insufficient": "❌ Insufficient balance!\nNeed {price} USDT\nCurrent: {balance} USDT",
        "insufficient_usdt": "❌ Insufficient USDT balance!\nNeed {price} USDT\nCurrent: {balance} USDT",
        "deposit_usdt_prompt": "💵 Enter the USDT amount to deposit (minimum 1 USDT):",
        "deposit_usdt_min": "❌ Minimum deposit is 1 USDT!",
        "deposit_usdt_invalid": "❌ Please enter a valid number!",
        "change_lang": "🌐 Change Language / Đổi ngôn ngữ",
        "back_to_menu": "🔙 Back to main menu",
        "email_prompt": "📧 Please send your **email (@gmail.com)** now:",
        "email_sent": "✅ Email has been sent to admin! We will process soon.",
        "email_invalid": "❌ Only @gmail.com emails are accepted! Please try again:",
        "reload_menu": "🔄 Reload Menu",
    }
}

def get_lang(user_id):
    user = get_user(user_id)
    return user.get("language", "vi")

def t(user_id, key, **kwargs):
    lang = get_lang(user_id)
    text = LANGUAGES.get(lang, LANGUAGES["vi"]).get(key, key)
    return text.format(**kwargs) if kwargs else text

def get_user(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id, 
            "username": None, 
            "first_name": None, 
            "balance": 0, 
            "balance_usdt": 0,
            "language": None,
            "joined_at": datetime.now(),
            "waiting_email_for": None
        }
        users.insert_one(user)
    return user

def update_balance(user_id, amount, currency="vnd"):
    if currency == "vnd":
        users.update_one({"user_id": user_id}, {"$inc": {"balance": amount}})
    else:
        users.update_one({"user_id": user_id}, {"$inc": {"balance_usdt": amount}})

def generate_order_code():
    return random.randint(10000000, 99999999)

def get_stock_count(category):
    stock_doc = stocks.find_one({"category": category})
    return len(stock_doc.get("accounts", [])) if stock_doc else 0

def notify_admin(order):
    user = get_user(order["user_id"])
    cat_info = CATEGORIES.get(order.get("category"), {})
    cat_name = cat_info.get("name", "Nạp tiền") if user.get("language") == "vi" else cat_info.get("name_en", "Deposit")
    
    if order["type"] == "deposit":
        text = f"""
💰 **ĐƠN NẠP TIỀN MỚI / NEW DEPOSIT**
Mã đơn/Order: #{order['order_code']}
User ID: `{order['user_id']}`
Tên/Name: {user.get('first_name', 'N/A')}
Số tiền/Amount: **{order['amount']:,}đ**
Trạng thái/Status: Chờ thanh toán/Pending
        """
    elif order["type"] == "deposit_usdt":
        text = f"""
💵 **ĐƠN NẠP USDT MỚI / NEW USDT DEPOSIT**
Mã đơn/Order: #{order['order_code']}
User ID: `{order['user_id']}`
Tên/Name: {user.get('first_name', 'N/A')}
Số USDT: **{order.get('amount_usdt', 0)} USDT** (~{order.get('amount_vnd', 0):,}đ)
Trạng thái/Status: Chờ thanh toán/Pending
        """
    else:
        text = f"""
🛒 **ĐƠN MUA HÀNG MỚI / NEW ORDER**
Mã đơn/Order: #{order['order_code']}
User ID: `{order['user_id']}`
Tên/Name: {user.get('first_name', 'N/A')}
Sản phẩm/Product: {cat_name}
Số tiền/Amount: **{order['amount']:,}đ**
Trạng thái/Status: Chờ thanh toán/Pending
        """
    try:
        bot.send_message(ADMIN_ID, text, parse_mode='Markdown')
    except Exception as e:
        print(f"Lỗi gửi thông báo admin: {e}")

# ================== /start ==================
@bot.message_handler(commands=['start'])
def start(message):
    user = get_user(message.from_user.id)
    
    users.update_one(
        {"user_id": message.from_user.id},
        {"$set": {
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "waiting_email_for": None
        }}
    )
    
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="lang_vi"),
        telebot.types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    
    current_lang = user.get("language")
    current_lang_text = ""
    if current_lang:
        current_lang_text = f"\n\nHiện tại/Current: {'🇻🇳 Tiếng Việt' if current_lang == 'vi' else '🇬🇧 English'}"
    
    bot.send_message(
        message.chat.id,
        f"🌐 **Chọn ngôn ngữ / Choose language**{current_lang_text}\n\n"
        "Vui lòng chọn ngôn ngữ bạn muốn sử dụng.\n"
        "Please choose your preferred language.",
        parse_mode='Markdown',
        reply_markup=markup
    )

def show_main_menu(chat_id, user_id, first_name):
    lang = get_lang(user_id)
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    
    for code, info in CATEGORIES.items():
        stock_count = get_stock_count(code)
        name = info["name"] if lang == "vi" else info["name_en"]
        
        if lang == "vi":
            price_text = f"{info['price']:,}đ"
        else:
            price_text = f"{info['price_usdt']} USDT"
        
        if stock_count > 0:
            stock_text = f" (còn {stock_count})" if lang == "vi" else f" ({stock_count} left)"
            markup.add(telebot.types.InlineKeyboardButton(
                f"🛒 {name} - {price_text}{stock_text}",
                callback_data=f"buy_{code}"
            ))
        else:
            markup.add(telebot.types.InlineKeyboardButton(
                f"{name} - 🔒 {'Hết hàng' if lang == 'vi' else 'Out of Stock'}",
                callback_data="outofstock"
            ))
    
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'wallet'), callback_data="my_wallet"))
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'deposit'), callback_data="deposit"))
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'deposit_usdt'), callback_data="deposit_usdt"))
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'change_lang'), callback_data="change_language"))
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'reload_menu'), callback_data="reload_menu"))
    
    bot.send_message(
        chat_id,
        t(user_id, 'welcome', name=first_name),
        parse_mode='Markdown',
        reply_markup=markup
    )

def handle_language_selection(call):
    lang = call.data.split("_")[1]
    user_id = call.from_user.id
    
    users.update_one(
        {"user_id": user_id},
        {"$set": {"language": lang}},
        upsert=True
    )
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    
    if lang == "vi":
        bot.send_message(call.message.chat.id, "✅ Đã chọn Tiếng Việt!")
    else:
        bot.send_message(call.message.chat.id, "✅ English selected!")
    
    show_main_menu(call.message.chat.id, user_id, call.from_user.first_name)

def change_language_menu(call):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="lang_vi"),
        telebot.types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    markup.add(telebot.types.InlineKeyboardButton(t(call.from_user.id, 'back_to_menu'), callback_data="back_to_menu"))
    
    current_lang = get_lang(call.from_user.id)
    bot.send_message(
        call.message.chat.id,
        f"🌐 **Chọn ngôn ngữ / Choose language**\n\n"
        f"Hiện tại/Current: {'🇻🇳 Tiếng Việt' if current_lang == 'vi' else '🇬🇧 English'}",
        parse_mode='Markdown',
        reply_markup=markup
    )

def show_wallet(call):
    user = get_user(call.from_user.id)
    lang = user.get("language", "vi")
    joined = user.get('joined_at', datetime.now()).strftime('%d/%m/%Y')
    
    if lang == "vi":
        text = f"""
🆔 **ID:** `{call.from_user.id}`
👤 **Tên:** {call.from_user.first_name or 'Không có tên'}
💰 **Số dư VND:** `{user.get('balance', 0):,}đ`
💵 **Số dư USDT:** `{user.get('balance_usdt', 0)} USDT`
📅 **Tham gia:** {joined}
        """
    else:
        text = f"""
🆔 **ID:** `{call.from_user.id}`
👤 **Name:** {call.from_user.first_name or 'No name'}
💰 **VND Balance:** `{user.get('balance', 0):,}đ`
💵 **USDT Balance:** `{user.get('balance_usdt', 0)} USDT`
📅 **Joined:** {joined}
        """
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(t(call.from_user.id, 'back_to_menu'), callback_data="back_to_menu"))
    
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

# ================== NẠP USDT QUA BINANCE ==================
def deposit_usdt_prompt(call):
    lang = get_lang(call.from_user.id)
    msg = t(call.from_user.id, 'deposit_usdt_prompt')
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(t(call.from_user.id, 'back_to_menu'), callback_data="back_to_menu"))
    
    bot.send_message(call.message.chat.id, msg, reply_markup=markup)
    bot.register_next_step_handler(call.message, process_deposit_usdt)

def process_deposit_usdt(message):
    user_id = message.from_user.id
    lang = get_lang(user_id)
    
    if message.text in ["/start", "/menu", "Quay lại", "Back"]:
        show_main_menu(message.chat.id, user_id, message.from_user.first_name)
        return
    
    try:
        amount_usdt = float(message.text.strip())
        
        if amount_usdt < 1:
            bot.reply_to(message, t(user_id, 'deposit_usdt_min'))
            bot.register_next_step_handler(message, process_deposit_usdt)
            return
        
        order_code = generate_order_code()
        amount_vnd = int(amount_usdt * USDT_RATE)
        
        order = {
            "order_code": order_code,
            "user_id": user_id,
            "type": "deposit_usdt",
            "amount_usdt": amount_usdt,
            "amount_vnd": amount_vnd,
            "amount": amount_vnd,
            "status": "pending",
            "binance_id": ADMIN_BINANCE_ID,
            "created_at": datetime.now()
        }
        orders.insert_one(order)
        
        notify_admin(order)
        
        if lang == "vi":
            msg = f"""
💱 **Nạp USDT qua Binance**

Mã đơn: #{order_code}
USDT: **{amount_usdt} USDT** (~{amount_vnd:,}đ)

🔸 Chuyển chính xác **{amount_usdt} USDT** đến Binance UID: `{ADMIN_BINANCE_ID}`
🔸 Ghi chú/Nội dung: **#{order_code}** (rất quan trọng!)

Sau khi chuyển khoản, admin sẽ duyệt và cộng USDT vào ví của bạn.
            """
        else:
            msg = f"""
💱 **Deposit via Binance USDT**

Order #: #{order_code}
USDT: **{amount_usdt} USDT** (~{amount_vnd:,} VND)

🔸 Transfer exactly **{amount_usdt} USDT** to Binance UID: `{ADMIN_BINANCE_ID}`
🔸 Note/Memo: **#{order_code}** (very important!)

After transfer, admin will approve and credit your wallet.
            """
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'back_to_menu'), callback_data="back_to_menu"))
        
        bot.send_message(message.chat.id, msg, parse_mode='Markdown', reply_markup=markup)
        
    except ValueError:
        bot.reply_to(message, t(user_id, 'deposit_usdt_invalid'))
        bot.register_next_step_handler(message, process_deposit_usdt)

# ================== NẠP TIỀN VND ==================
def deposit_menu(call):
    lang = get_lang(call.from_user.id)
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("50.000đ", callback_data="deposit_50000"))
    markup.add(telebot.types.InlineKeyboardButton("100.000đ", callback_data="deposit_100000"))
    markup.add(telebot.types.InlineKeyboardButton("200.000đ", callback_data="deposit_200000"))
    markup.add(telebot.types.InlineKeyboardButton(
        "Nhập số khác" if lang == "vi" else "Custom amount", 
        callback_data="deposit_custom"
    ))
    markup.add(telebot.types.InlineKeyboardButton(t(call.from_user.id, 'back_to_menu'), callback_data="back_to_menu"))
    
    msg = "💳 Chọn số tiền muốn nạp vào ví:" if lang == "vi" else "💳 Choose amount to deposit:"
    bot.send_message(call.message.chat.id, msg, reply_markup=markup)

def handle_deposit_amount(call):
    lang = get_lang(call.from_user.id)
    if call.data == "deposit_custom":
        msg = "Nhập số tiền muốn nạp (tối thiểu 2.000đ):" if lang == "vi" else "Enter deposit amount (min 2,000 VND):"
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(t(call.from_user.id, 'back_to_menu'), callback_data="back_to_menu"))
        
        bot.send_message(call.message.chat.id, msg, reply_markup=markup)
        bot.register_next_step_handler(call.message, process_custom_deposit)
        return
    try:
        amount = int(call.data.split("_")[1])
        create_deposit_payment(call.message.chat.id, call.from_user.id, amount)
    except:
        bot.send_message(call.message.chat.id, "❌ Có lỗi khi xử lý." if lang == "vi" else "❌ Processing error.")

def process_custom_deposit(message):
    user_id = message.from_user.id
    lang = get_lang(user_id)
    
    if message.text in ["/start", "/menu", "Quay lại", "Back"]:
        show_main_menu(message.chat.id, user_id, message.from_user.first_name)
        return
    
    try:
        amount = int(message.text.strip())
        if amount < 2000:
            msg = "❌ Số tiền tối thiểu là 2.000đ!" if lang == "vi" else "❌ Minimum amount is 2,000 VND!"
            return bot.reply_to(message, msg)
        create_deposit_payment(message.chat.id, user_id, amount)
    except ValueError:
        msg = "❌ Vui lòng nhập số tiền hợp lệ!" if lang == "vi" else "❌ Please enter a valid amount!"
        bot.reply_to(message, msg)
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi/Error: {str(e)}")

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
        description=f"Nap #{order_code}",
        return_url="https://t.me/" + bot.get_me().username,
        cancel_url="https://t.me/" + bot.get_me().username
    )
    payment_link = payos.payment_requests.create(payment_data)

    lang = get_lang(user_id)
    if lang == "vi":
        msg = f"""
💰 **Nạp tiền vào ví**

Mã đơn: #{order_code}
Số tiền: **{amount:,}đ**

🔗 [Thanh toán ngay]({payment_link.checkout_url})
        """
    else:
        msg = f"""
💰 **Deposit to Wallet**

Order code: #{order_code}
Amount: **{amount:,} VND**

🔗 [Pay now]({payment_link.checkout_url})
        """
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'back_to_menu'), callback_data="back_to_menu"))
    
    bot.send_message(chat_id, msg, parse_mode='Markdown', reply_markup=markup)

# ================== MUA HÀNG ==================
def handle_buy(call):
    code = call.data.split("_")[1]
    info = CATEGORIES.get(code)
    user_id = call.from_user.id
    lang = get_lang(user_id)
    
    if not info:
        msg = "❌ Sản phẩm không tồn tại!" if lang == "vi" else "❌ Product does not exist!"
        return bot.send_message(call.message.chat.id, msg)

    user = get_user(user_id)
    stock_count = get_stock_count(code)

    if stock_count <= 0:
        msg = "❌ Sản phẩm đã hết hàng!" if lang == "vi" else "❌ Product is out of stock!"
        return bot.send_message(call.message.chat.id, msg)

    if lang == "vi":
        price = info["price"]
        currency = "vnd"
        balance = user.get("balance", 0)
        price_display = f"{price:,}đ"
    else:
        price = info["price_usdt"]
        currency = "usdt"
        balance = user.get("balance_usdt", 0)
        price_display = f"{price} USDT"

    if balance < price:
        product_name = info["name"] if lang == "vi" else info["name_en"]
        
        if lang == "vi":
            msg = f"""
❌ **Số dư ví không đủ!**

🛒 Sản phẩm: **{product_name}**
💳 Giá: **{price_display}**
💰 Số dư hiện tại: **{user.get('balance', 0):,}đ** (VND) | **{user.get('balance_usdt', 0)} USDT**

Vui lòng nạp thêm tiền vào ví để tiếp tục mua hàng.
            """
        else:
            msg = f"""
❌ **Insufficient balance!**

🛒 Product: **{product_name}**
💳 Price: **{price_display}**
💰 Current balance: **{user.get('balance', 0):,} VND** | **{user.get('balance_usdt', 0)} USDT**

Please deposit more funds to continue.
            """
        
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        markup.add(telebot.types.InlineKeyboardButton(
            t(user_id, 'deposit'), callback_data="deposit"
        ))
        markup.add(telebot.types.InlineKeyboardButton(
            t(user_id, 'deposit_usdt'), callback_data="deposit_usdt"
        ))
        markup.add(telebot.types.InlineKeyboardButton(
            t(user_id, 'back_to_menu'), callback_data="back_to_menu"
        ))
        
        bot.send_message(call.message.chat.id, msg, parse_mode='Markdown', reply_markup=markup)
        return

    if code in ["canva1slot", "youtube1slot"]:
        update_balance(user_id, -price, currency)

        order_code = generate_order_code()
        order = {
            "order_code": order_code,
            "user_id": user_id,
            "category": code,
            "amount": info["price"],
            "amount_usdt": info["price_usdt"],
            "type": code,
            "currency_used": currency,
            "status": "waiting_email",
            "created_at": datetime.now()
        }
        orders.insert_one(order)
        notify_admin(order)

        stock_doc = stocks.find_one({"category": code})
        if stock_doc and stock_doc.get("accounts"):
            stock_doc["accounts"].pop(0)
            stocks.update_one({"category": code}, {"$set": {"accounts": stock_doc["accounts"]}})

        users.update_one(
            {"user_id": user_id}, 
            {"$set": {"waiting_email_for": order_code}}
        )

        product_name = info["name"] if lang == "vi" else info["name_en"]
        new_balance = balance - price
        
        if lang == "vi":
            msg = f"""
✅ **Đã trừ {price_display} từ ví!**

🛒 Sản phẩm: **{product_name}**
💰 Số dư còn lại: **{new_balance:,}đ**

📧 Vui lòng gửi **email (@gmail.com)** của bạn ngay bây giờ để admin thêm vào slot.
            """
        else:
            msg = f"""
✅ **Deducted {price_display} from wallet!**

🛒 Product: **{product_name}**
💰 Remaining balance: **{new_balance} USDT**

📧 Please send your **email (@gmail.com)** now for admin to add you to the slot.
            """
        bot.send_message(call.message.chat.id, msg, parse_mode='Markdown')
        return

    update_balance(user_id, -price, currency)
    
    stock_doc = stocks.find_one({"category": code})
    
    if not stock_doc or not stock_doc.get("accounts"):
        update_balance(user_id, price, currency)
        
        if lang == "vi":
            msg = "❌ Rất tiếc, sản phẩm vừa hết hàng! Tiền đã được hoàn vào ví."
        else:
            msg = "❌ Sorry, product just went out of stock! Money has been refunded to your wallet."
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'back_to_menu'), callback_data="back_to_menu"))
        
        bot.send_message(call.message.chat.id, msg, reply_markup=markup)
        return
    
    account = stock_doc["accounts"].pop(0)
    stocks.update_one({"category": code}, {"$set": {"accounts": stock_doc["accounts"]}})
    
    product_name = info["name"] if lang == "vi" else info["name_en"]
    new_balance = balance - price
    
    order_code = generate_order_code()
    order = {
        "order_code": order_code,
        "user_id": user_id,
        "category": code,
        "amount": info["price"],
        "amount_usdt": info["price_usdt"],
        "type": "purchase",
        "currency_used": currency,
        "status": "delivered",
        "account": account,
        "created_at": datetime.now(),
        "delivered_at": datetime.now()
    }
    orders.insert_one(order)
    
    if lang == "vi":
        msg = f"""
🎉 **MUA THÀNH CÔNG!**

📦 Mã đơn: **#{order_code}**
🛒 Sản phẩm: **{product_name}**
💰 Giá: **{price_display}**

🔐 **Tài khoản của bạn:**
`{account}`

💵 Số dư còn lại: **{new_balance:,}đ**

Cảm ơn bạn đã mua hàng! 🎊
        """
    else:
        msg = f"""
🎉 **PURCHASE SUCCESSFUL!**

📦 Order ID: **#{order_code}**
🛒 Product: **{product_name}**
💰 Price: **{price_display}**

🔐 **Your account:**
`{account}`

💵 Remaining balance: **{new_balance} USDT**

Thank you for your purchase! 🎊
        """
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'back_to_menu'), callback_data="back_to_menu"))
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'wallet'), callback_data="my_wallet"))
    
    bot.send_message(call.message.chat.id, msg, parse_mode='Markdown', reply_markup=markup)

# ================== ADMIN COMMANDS ==================
@bot.message_handler(commands=['admin'])
def admin_help(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    help_text = """
🔧 **ADMIN COMMANDS**

📊 **Quản lý user:**
/danhsach - Xem danh sách tất cả người dùng
/xoasodu <user_id> [vnd|usdt|all] - Xóa số dư 1 user
/xoasoduall [vnd|usdt|all] - Xóa số dư TẤT CẢ user (có xác nhận)
/addbalance <user_id> <số> [vnd|usdt] - Cộng tiền
/resetallbalance - Reset tất cả số dư (có xác nhận)

💰 **Quản lý nạp:**
/duyetnap <mã> - Duyệt nạp VND
/duyetnapusdt <mã> - Duyệt nạp USDT

📦 **Quản lý đơn hàng:**
/giao <mã> - Giao tài khoản

🔧 **Quản lý stock:**
/setcanva <số> - Set số lượng Canva 1 Slot
/setyoutube <số> - Set số lượng YouTube 1 Slot
/sethotspot <số> - Set số lượng Hotspot
/setgemini <số> - Set số lượng Gemini
/setcapcut <số> - Set số lượng CapCut
/stock - Xem tồn kho hiện tại

📤 **Upload tài khoản:**
/upload_canva - Upload file txt cho Canva
/upload_youtube - Upload file txt cho YouTube
/upload_hotspot - Upload file txt cho Hotspot
/upload_gemini - Upload file txt cho Gemini
/upload_capcut - Upload file txt cho CapCut

⚙️ **Cài đặt:**
/setusdtrate <tỷ_giá> - Cập nhật tỷ giá USDT
/setprice <mã> <giá_VND> <giá_USDT> - Sửa giá sản phẩm

📢 **Thông báo:**
/broadcast <nội_dung> - Gửi thông báo đến tất cả user
/reload - Load lại menu (dùng cho user)
    """
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['danhsach'])
def admin_danhsach(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    try:
        all_users = list(users.find())
        
        if not all_users:
            bot.reply_to(message, "📊 Chưa có người dùng nào.")
            return
        
        all_users.sort(key=lambda x: x.get('balance', 0), reverse=True)
        
        total_users = len(all_users)
        total_balance_vnd = sum(u.get('balance', 0) for u in all_users)
        total_balance_usdt = sum(u.get('balance_usdt', 0) for u in all_users)
        
        text = f"📊 **DANH SÁCH NGƯỜI DÙNG**\n"
        text += f"👥 Tổng số: **{total_users}** người dùng\n"
        text += f"💰 Tổng VND: **{total_balance_vnd:,}đ**\n"
        text += f"💵 Tổng USDT: **{total_balance_usdt} USDT**\n"
        text += "──────────────────────────────\n\n"
        
        part = 1
        current_text = text
        
        for idx, u in enumerate(all_users, 1):
            user_id = u.get('user_id', 'N/A')
            first_name = u.get('first_name', 'Không tên')
            username = u.get('username', '')
            balance_vnd = u.get('balance', 0)
            balance_usdt = u.get('balance_usdt', 0)
            lang = u.get('language', 'vi')
            joined = u.get('joined_at', datetime.now()).strftime('%d/%m/%Y')
            
            if username:
                display_name = f"{first_name} (@{username})"
            else:
                display_name = first_name
            
            user_info = f"**{idx}.** {display_name}\n"
            user_info += f"   🆔 `{user_id}`\n"
            user_info += f"   💰 VND: `{balance_vnd:,}đ` | USDT: `{balance_usdt}`\n"
            user_info += f"   🌐 {lang.upper()} | 📅 {joined}\n\n"
            
            if len(current_text + user_info) > 3500:
                bot.send_message(message.chat.id, current_text, parse_mode='Markdown')
                current_text = f"📊 **DANH SÁCH NGƯỜI DÙNG (Phần {part+1})**\n\n"
                part += 1
            
            current_text += user_info
        
        if current_text:
            bot.send_message(message.chat.id, current_text, parse_mode='Markdown')
            
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")
        print(f"Lỗi lệnh danhsach: {e}")

@bot.message_handler(commands=['xoasodu'])
def admin_xoa_so_du(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /xoasodu <user_id> [vnd|usdt|all]\nVí dụ:\n- /xoasodu 123456789 vnd (chỉ xóa VND)\n- /xoasodu 123456789 usdt (chỉ xóa USDT)\n- /xoasodu 123456789 all (xóa cả hai)")
            return
        
        user_id = int(parts[1])
        currency = parts[2].lower() if len(parts) > 2 else "all"
        
        user = get_user(user_id)
        if not user:
            bot.reply_to(message, f"❌ Không tìm thấy user với ID `{user_id}`!")
            return
        
        old_vnd = user.get('balance', 0)
        old_usdt = user.get('balance_usdt', 0)
        
        if currency == "vnd":
            if old_vnd == 0:
                bot.reply_to(message, f"ℹ️ User `{user_id}` đã có 0đ VND!")
                return
            update_balance(user_id, -old_vnd, "vnd")
            bot.reply_to(
                message, 
                f"✅ Đã xóa **{old_vnd:,}đ** VND của user `{user_id}`!\n"
                f"👤 {user.get('first_name', 'N/A')}\n"
                f"💰 Số dư VND mới: **0đ**\n"
                f"💵 Số dư USDT giữ nguyên: **{old_usdt} USDT**"
            )
            
        elif currency == "usdt":
            if old_usdt == 0:
                bot.reply_to(message, f"ℹ️ User `{user_id}` đã có 0 USDT!")
                return
            update_balance(user_id, -old_usdt, "usdt")
            bot.reply_to(
                message, 
                f"✅ Đã xóa **{old_usdt} USDT** của user `{user_id}`!\n"
                f"👤 {user.get('first_name', 'N/A')}\n"
                f"💰 Số dư VND giữ nguyên: **{old_vnd:,}đ**\n"
                f"💵 Số dư USDT mới: **0 USDT**"
            )
            
        else:
            if old_vnd == 0 and old_usdt == 0:
                bot.reply_to(message, f"ℹ️ User `{user_id}` đã có 0đ và 0 USDT!")
                return
            
            update_balance(user_id, -old_vnd, "vnd")
            update_balance(user_id, -old_usdt, "usdt")
            bot.reply_to(
                message, 
                f"✅ Đã xóa toàn bộ số dư của user `{user_id}`!\n"
                f"👤 {user.get('first_name', 'N/A')}\n"
                f"💰 VND đã xóa: **{old_vnd:,}đ** → 0đ\n"
                f"💵 USDT đã xóa: **{old_usdt}** → 0 USDT"
            )
            
    except ValueError:
        bot.reply_to(message, "❌ ID người dùng không hợp lệ!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['xoasoduall'])
def admin_xoa_so_du_all(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    try:
        parts = message.text.split()
        currency = parts[1].lower() if len(parts) > 1 else "all"
        
        if currency not in ["vnd", "usdt", "all"]:
            bot.reply_to(message, "❌ Tham số không hợp lệ! Sử dụng: vnd, usdt, hoặc all")
            return
        
        total_users = users.count_documents({})
        
        if currency == "vnd":
            total_balance = sum(u.get('balance', 0) for u in users.find())
            if total_balance == 0:
                bot.reply_to(message, "ℹ️ Tất cả user đã có 0đ VND!")
                return
            confirm_text = f"⚠️ **XÁC NHẬN XÓA TOÀN BỘ SỐ DƯ VND**\n\n👥 Số user bị ảnh hưởng: **{total_users}**\n💰 Tổng VND sẽ xóa: **{total_balance:,}đ**\n\nBạn có chắc chắn muốn xóa?"
        elif currency == "usdt":
            total_balance = sum(u.get('balance_usdt', 0) for u in users.find())
            if total_balance == 0:
                bot.reply_to(message, "ℹ️ Tất cả user đã có 0 USDT!")
                return
            confirm_text = f"⚠️ **XÁC NHẬN XÓA TOÀN BỘ SỐ DƯ USDT**\n\n👥 Số user bị ảnh hưởng: **{total_users}**\n💵 Tổng USDT sẽ xóa: **{total_balance} USDT**\n\nBạn có chắc chắn muốn xóa?"
        else:
            total_vnd = sum(u.get('balance', 0) for u in users.find())
            total_usdt = sum(u.get('balance_usdt', 0) for u in users.find())
            if total_vnd == 0 and total_usdt == 0:
                bot.reply_to(message, "ℹ️ Tất cả user đã có 0đ và 0 USDT!")
                return
            confirm_text = f"⚠️ **XÁC NHẬN XÓA TOÀN BỘ SỐ DƯ (VND + USDT)**\n\n👥 Số user bị ảnh hưởng: **{total_users}**\n💰 Tổng VND sẽ xóa: **{total_vnd:,}đ**\n💵 Tổng USDT sẽ xóa: **{total_usdt} USDT**\n\nBạn có chắc chắn muốn xóa?"
        
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            telebot.types.InlineKeyboardButton("✅ XÁC NHẬN", callback_data=f"confirm_xoasoduall_{currency}"),
            telebot.types.InlineKeyboardButton("❌ HỦY", callback_data="cancel_xoasoduall")
        )
        
        bot.reply_to(message, confirm_text, reply_markup=markup, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['stock'])
def admin_view_stock(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    text = "📦 **TỒN KHO HIỆN TẠI**\n\n"
    
    for code, info in CATEGORIES.items():
        stock_count = get_stock_count(code)
        name = info["name"]
        text += f"📌 {name}: **{stock_count}** tài khoản\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['setcanva'])
def admin_set_canva(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /setcanva <số_lượng>")
            return
        
        count = int(parts[1])
        if count < 0:
            bot.reply_to(message, "❌ Số lượng không được âm!")
            return
        
        accounts = ["Slot sẵn sàng"] * count
        stocks.update_one(
            {"category": "canva1slot"}, 
            {"$set": {"accounts": accounts}}, 
            upsert=True
        )
        bot.reply_to(message, f"✅ Đã set Canva 1 Slot về **{count} slot**!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /setcanva <số_lượng>")

@bot.message_handler(commands=['setyoutube'])
def admin_set_youtube(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /setyoutube <số_lượng>")
            return
        
        count = int(parts[1])
        if count < 0:
            bot.reply_to(message, "❌ Số lượng không được âm!")
            return
        
        accounts = ["Slot sẵn sàng"] * count
        stocks.update_one(
            {"category": "youtube1slot"}, 
            {"$set": {"accounts": accounts}}, 
            upsert=True
        )
        bot.reply_to(message, f"✅ Đã set YouTube 1 Slot về **{count} slot**!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /setyoutube <số_lượng>")

@bot.message_handler(commands=['sethotspot'])
def admin_set_hotspot(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /sethotspot <số_lượng>")
            return
        
        count = int(parts[1])
        if count < 0:
            bot.reply_to(message, "❌ Số lượng không được âm!")
            return
        
        accounts = ["Slot sẵn sàng"] * count
        stocks.update_one(
            {"category": "hotspot"}, 
            {"$set": {"accounts": accounts}}, 
            upsert=True
        )
        bot.reply_to(message, f"✅ Đã set Hotspot về **{count} tài khoản**!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /sethotspot <số_lượng>")

@bot.message_handler(commands=['setgemini'])
def admin_set_gemini(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /setgemini <số_lượng>")
            return
        
        count = int(parts[1])
        if count < 0:
            bot.reply_to(message, "❌ Số lượng không được âm!")
            return
        
        accounts = ["Slot sẵn sàng"] * count
        stocks.update_one(
            {"category": "gemini"}, 
            {"$set": {"accounts": accounts}}, 
            upsert=True
        )
        bot.reply_to(message, f"✅ Đã set Gemini về **{count} tài khoản**!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /setgemini <số_lượng>")

@bot.message_handler(commands=['setcapcut'])
def admin_set_capcut(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /setcapcut <số_lượng>")
            return
        
        count = int(parts[1])
        if count < 0:
            bot.reply_to(message, "❌ Số lượng không được âm!")
            return
        
        accounts = ["Slot sẵn sàng"] * count
        stocks.update_one(
            {"category": "capcut"}, 
            {"$set": {"accounts": accounts}}, 
            upsert=True
        )
        bot.reply_to(message, f"✅ Đã set CapCut về **{count} tài khoản**!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /setcapcut <số_lượng>")

@bot.message_handler(commands=['setprice'])
def admin_set_price(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 4:
            bot.reply_to(
                message, 
                "📝 **Sử dụng:** `/setprice <mã> <giá_VND> <giá_USDT>`\n\n"
                "**Danh sách mã sản phẩm:**\n"
                "• `hotspot` - Hotspot Shield 7D\n"
                "• `gemini` - Gemini Pro\n"
                "• `capcut` - CapCut Pro\n"
                "• `canva1slot` - Canva 1 Slot\n"
                "• `canva100slot` - Canva 100 Slot\n"
                "• `youtube1slot` - YouTube 1 Slot\n\n"
                "**Ví dụ:** `/setprice hotspot 3000 0.12`",
                parse_mode='Markdown'
            )
            return
        
        code = parts[1].lower()
        price_vnd = int(parts[2])
        price_usdt = float(parts[3])
        
        if code not in CATEGORIES:
            bot.reply_to(message, f"❌ Mã sản phẩm `{code}` không tồn tại!")
            return
        
        if price_vnd < 0 or price_usdt < 0:
            bot.reply_to(message, "❌ Giá không được âm!")
            return
        
        CATEGORIES[code]["price"] = price_vnd
        CATEGORIES[code]["price_usdt"] = price_usdt
        
        categories.update_one(
            {"code": code},
            {"$set": {
                "price": price_vnd,
                "price_usdt": price_usdt
            }}
        )
        
        product_name = CATEGORIES[code]["name"]
        bot.reply_to(
            message,
            f"✅ **Đã cập nhật giá sản phẩm!**\n\n"
            f"📦 Sản phẩm: **{product_name}**\n"
            f"💰 Giá VND: **{price_vnd:,}đ**\n"
            f"💵 Giá USDT: **{price_usdt} USDT**",
            parse_mode='Markdown'
        )
        
    except ValueError:
        bot.reply_to(message, "❌ Giá phải là số!\nVí dụ: `/setprice hotspot 3000 0.12`")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['reload'])
def reload_menu(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user.get("language"):
        start(message)
        return
    
    show_main_menu(message.chat.id, user_id, message.from_user.first_name)
    
    lang = user.get("language", "vi")
    if lang == "vi":
        bot.reply_to(message, "🔄 Đã tải lại menu sản phẩm!", reply_markup=telebot.types.ReplyKeyboardRemove())
    else:
        bot.reply_to(message, "🔄 Menu reloaded!", reply_markup=telebot.types.ReplyKeyboardRemove())

@bot.message_handler(commands=['broadcast'])
def admin_broadcast(message):
    global pending_broadcast
    
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(
            message,
            "📢 **Sử dụng:** `/broadcast <nội dung>`\n\n"
            "**Hỗ trợ Markdown:**\n"
            "• `*in đậm*` → *in đậm*\n"
            "• `_in nghiêng_` → _in nghiêng_\n"
            "• `[text](link)` → [text](link)\n\n"
            "**Ví dụ:** `/broadcast Chào mừng sản phẩm mới!`",
            parse_mode='Markdown'
        )
        return
    
    broadcast_text = parts[1]
    
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("✅ GỬI NGAY", callback_data="confirm_broadcast"),
        telebot.types.InlineKeyboardButton("📝 XEM TRƯỚC", callback_data="preview_broadcast"),
        telebot.types.InlineKeyboardButton("❌ HỦY", callback_data="cancel_broadcast")
    )
    
    pending_broadcast = {
        "admin_id": message.from_user.id,
        "text": broadcast_text,
        "timestamp": datetime.now()
    }
    
    total_users = users.count_documents({})
    
    bot.reply_to(
        message,
        f"📢 **XÁC NHẬN GỬI THÔNG BÁO**\n\n"
        f"👥 Số người nhận: **{total_users}**\n\n"
        f"📝 **Nội dung:**\n{broadcast_text}\n\n"
        f"Chọn hành động bên dưới:",
        parse_mode='Markdown',
        reply_markup=markup
    )

def handle_confirm_broadcast(call):
    global pending_broadcast
    
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Không có quyền!", show_alert=True)
        return
    
    if not pending_broadcast:
        bot.edit_message_text("❌ Không có thông báo nào đang chờ!", call.message.chat.id, call.message.message_id)
        return
    
    broadcast_text = pending_broadcast["text"]
    
    all_users = list(users.find({}, {"user_id": 1}))
    total_users = len(all_users)
    
    success_count = 0
    fail_count = 0
    
    for user_doc in all_users:
        user_id = user_doc.get("user_id")
        if not user_id:
            continue
        
        try:
            bot.send_message(
                user_id,
                f"📢 **THÔNG BÁO TỪ ADMIN**\n\n{broadcast_text}",
                parse_mode='Markdown'
            )
            success_count += 1
            time.sleep(0.05)
        except Exception as e:
            fail_count += 1
            print(f"Lỗi gửi broadcast đến {user_id}: {e}")
    
    bot.edit_message_text(
        f"✅ **ĐÃ GỬI THÔNG BÁO XONG!**\n\n"
        f"📊 **Kết quả:**\n"
        f"✅ Thành công: **{success_count}**\n"
        f"❌ Thất bại: **{fail_count}**\n"
        f"👥 Tổng: **{total_users}**\n\n"
        f"📝 **Nội dung đã gửi:**\n{broadcast_text}",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )
    
    pending_broadcast = None
    bot.answer_callback_query(call.id, f"✅ Đã gửi thành công {success_count}/{total_users} người dùng!")

def handle_preview_broadcast(call):
    global pending_broadcast
    
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Không có quyền!", show_alert=True)
        return
    
    if not pending_broadcast:
        bot.answer_callback_query(call.id, "❌ Không có thông báo nào đang chờ!", show_alert=True)
        return
    
    broadcast_text = pending_broadcast["text"]
    
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("✅ GỬI NGAY", callback_data="confirm_broadcast"),
        telebot.types.InlineKeyboardButton("❌ HỦY", callback_data="cancel_broadcast")
    )
    
    total_users = users.count_documents({})
    
    bot.edit_message_text(
        f"📢 **XEM TRƯỚC THÔNG BÁO**\n\n"
        f"👥 Số người nhận: **{total_users}**\n\n"
        f"📝 **Nội dung sẽ hiển thị:**\n\n"
        f"---\n"
        f"📢 **THÔNG BÁO TỪ ADMIN**\n\n{broadcast_text}\n"
        f"---\n\n"
        f"Chọn hành động:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    
    bot.answer_callback_query(call.id, "📝 Đây là bản xem trước")

def handle_cancel_broadcast(call):
    global pending_broadcast
    
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Không có quyền!", show_alert=True)
        return
    
    pending_broadcast = None
    
    bot.edit_message_text(
        "❌ **Đã hủy gửi thông báo!**",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )
    
    bot.answer_callback_query(call.id, "Đã hủy")

@bot.message_handler(commands=['upload_canva', 'upload_youtube', 'upload_hotspot', 'upload_gemini', 'upload_capcut'])
def admin_upload_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    cmd = message.text.split()[0].split('_')[1]
    
    category_map = {
        "canva": "canva1slot",
        "youtube": "youtube1slot",
        "hotspot": "hotspot",
        "gemini": "gemini",
        "capcut": "capcut"
    }
    
    category = category_map.get(cmd)
    if not category:
        return
    
    pending_uploads.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"category": category, "timestamp": datetime.now()}},
        upsert=True
    )
    
    product_name = CATEGORIES[category]["name"]
    bot.reply_to(
        message, 
        f"📤 Vui lòng gửi file .txt chứa danh sách tài khoản cho **{product_name}**\n"
        f"Mỗi dòng là một tài khoản (định dạng: `email|password` hoặc `username|password` hoặc tài khoản đơn)"
    )

@bot.message_handler(commands=['duyetnap'])
def admin_duyet_nap(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /duyetnap <mã đơn>")
            return
        
        order_code = int(parts[1])
        order = orders.find_one({"order_code": order_code, "type": "deposit", "status": "pending"})
        if not order:
            bot.reply_to(message, "❌ Không tìm thấy đơn nạp pending!")
            return
        
        user_id = order['user_id']
        amount = order['amount']
        update_balance(user_id, amount)
        orders.update_one({"order_code": order_code}, {"$set": {"status": "approved", "approved_at": datetime.now()}})
        
        user = get_user(user_id)
        lang = user.get("language", "vi")
        if lang == "vi":
            msg = f"✅ Nạp tiền đã được duyệt!\nSố tiền: +{amount:,}đ\nSố dư hiện tại: {get_user(user_id)['balance']:,}đ"
        else:
            msg = f"✅ Deposit approved!\nAmount: +{amount:,} VND\nCurrent balance: {get_user(user_id)['balance']:,} VND"
        
        bot.send_message(user_id, msg)
        bot.reply_to(message, f"✅ Đã duyệt nạp tiền #{order_code} - Cộng {amount:,}đ cho user {user_id}")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /duyetnap <mã đơn>")

@bot.message_handler(commands=['duyetnapusdt'])
def admin_duyet_nap_usdt(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /duyetnapusdt <mã đơn>")
            return
        
        order_code = int(parts[1])
        order = orders.find_one({"order_code": order_code, "type": "deposit_usdt", "status": "pending"})
        if not order:
            bot.reply_to(message, "❌ Không tìm thấy đơn nạp USDT pending!")
            return
        
        user_id = order['user_id']
        amount_usdt = order['amount_usdt']
        
        update_balance(user_id, amount_usdt, "usdt")
        orders.update_one({"order_code": order_code}, {"$set": {"status": "approved", "approved_at": datetime.now()}})
        
        user = get_user(user_id)
        lang = user.get("language", "vi")
        if lang == "vi":
            msg = f"✅ Nạp USDT đã được duyệt!\nSố tiền: +{amount_usdt} USDT\nSố dư USDT hiện tại: {get_user(user_id)['balance_usdt']} USDT"
        else:
            msg = f"✅ USDT deposit approved!\nAmount: +{amount_usdt} USDT\nCurrent USDT balance: {get_user(user_id)['balance_usdt']} USDT"
        
        bot.send_message(user_id, msg)
        bot.reply_to(message, f"✅ Đã duyệt nạp USDT #{order_code} - Cộng {amount_usdt} USDT cho user {user_id}")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /duyetnapusdt <mã đơn>")

@bot.message_handler(commands=['giao'])
def admin_giao(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /giao <mã đơn>")
            return
        
        order_code = int(parts[1])
        order = orders.find_one({"order_code": order_code})
        if not order:
            bot.reply_to(message, "❌ Không tìm thấy đơn!")
            return
        
        category = order.get("category")
        user_id = order["user_id"]
        stock_doc = stocks.find_one({"category": category})
        
        if not stock_doc or not stock_doc.get("accounts"):
            bot.reply_to(message, "❌ Hết stock loại này!")
            return
        
        account = stock_doc["accounts"].pop(0)
        stocks.update_one({"category": category}, {"$set": {"accounts": stock_doc["accounts"]}})
        
        user = get_user(user_id)
        lang = user.get("language", "vi")
        product_name = CATEGORIES.get(category, {}).get("name" if lang == "vi" else "name_en", category)
        
        if lang == "vi":
            msg = f"""
🎉 **Tài khoản đã được giao!**

Đơn: #{order_code}
Sản phẩm: {product_name}
Tài khoản: `{account}`
            """
        else:
            msg = f"""
🎉 **Account delivered!**

Order: #{order_code}
Product: {product_name}
Account: `{account}`
            """
        bot.send_message(user_id, msg, parse_mode='Markdown')
        orders.update_one({"order_code": order_code}, {"$set": {"status": "delivered", "delivered_at": datetime.now(), "account": account}})
        bot.reply_to(message, f"✅ Đã giao thành công đơn #{order_code}")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /giao <mã đơn>")

@bot.message_handler(commands=['addbalance'])
def admin_add_balance(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "Sử dụng: /addbalance <user_id> <số_tiền> [vnd|usdt]")
            return
        
        user_id = int(parts[1])
        amount = float(parts[2]) if '.' in parts[2] else int(parts[2])
        currency = parts[3].lower() if len(parts) > 3 else "vnd"
        
        if currency not in ["vnd", "usdt"]:
            bot.reply_to(message, "Currency phải là 'vnd' hoặc 'usdt'")
            return
        
        update_balance(user_id, amount, currency)
        
        user = get_user(user_id)
        if currency == "vnd":
            bot.reply_to(message, f"✅ Đã cộng {amount:,}đ cho user {user_id}\nSố dư mới: {user['balance']:,}đ")
        else:
            bot.reply_to(message, f"✅ Đã cộng {amount} USDT cho user {user_id}\nSố dư mới: {user['balance_usdt']} USDT")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /addbalance <user_id> <số_tiền> [vnd|usdt]")

@bot.message_handler(commands=['resetallbalance'])
def admin_reset_all_balance(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ Xác nhận reset tất cả", callback_data="confirm_reset_all"))
    markup.add(telebot.types.InlineKeyboardButton("❌ Hủy", callback_data="cancel_reset_all"))
    bot.reply_to(message, "⚠️ Bạn sắp reset số dư về 0 cho **TẤT CẢ** user (cả VND và USDT). Xác nhận?", reply_markup=markup)

@bot.message_handler(commands=['setusdtrate'])
def admin_set_usdt_rate(message):
    global USDT_RATE
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /setusdtrate <tỷ_giá>")
            return
        
        new_rate = int(parts[1])
        USDT_RATE = new_rate
        bot.reply_to(message, f"✅ Đã cập nhật tỷ giá: 1 USDT = {new_rate:,}đ")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /setusdtrate <tỷ_giá>")

# ================== HANDLER CHO DOCUMENT (FILE UPLOAD) ==================
@bot.message_handler(content_types=['document'])
def handle_document(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    pending = pending_uploads.find_one({"user_id": message.from_user.id})
    if not pending:
        bot.reply_to(message, "❌ Bạn chưa dùng lệnh upload nào! Hãy dùng /upload_canva, /upload_youtube, v.v... trước.")
        return
    
    category = pending.get("category")
    if not category:
        return
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        content = downloaded_file.decode('utf-8')
        accounts = [line.strip() for line in content.split('\n') if line.strip()]
        
        if not accounts:
            bot.reply_to(message, "❌ File trống hoặc không có tài khoản hợp lệ!")
            return
        
        stock_doc = stocks.find_one({"category": category})
        if stock_doc:
            existing_accounts = stock_doc.get("accounts", [])
            existing_accounts.extend(accounts)
            stocks.update_one(
                {"category": category},
                {"$set": {"accounts": existing_accounts}}
            )
        else:
            stocks.insert_one({"category": category, "accounts": accounts})
        
        pending_uploads.delete_one({"user_id": message.from_user.id})
        
        product_name = CATEGORIES[category]["name"]
        bot.reply_to(
            message, 
            f"✅ Đã thêm **{len(accounts)}** tài khoản vào **{product_name}**!\n"
            f"Tổng số tài khoản hiện tại: **{get_stock_count(category)}**"
        )
        
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi khi xử lý file: {str(e)}")

# ================== CALLBACK HANDLER ==================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    try:
        if call.data.startswith("lang_"):
            handle_language_selection(call)
        elif call.data == "change_language":
            change_language_menu(call)
        elif call.data == "my_wallet":
            show_wallet(call)
        elif call.data == "deposit":
            deposit_menu(call)
        elif call.data == "deposit_usdt":
            deposit_usdt_prompt(call)
        elif call.data == "back_to_menu":
            show_main_menu(call.message.chat.id, call.from_user.id, call.from_user.first_name)
        elif call.data == "reload_menu":
            bot.delete_message(call.message.chat.id, call.message.message_id)
            show_main_menu(call.message.chat.id, call.from_user.id, call.from_user.first_name)
            lang = get_lang(call.from_user.id)
            bot.answer_callback_query(call.id, 
                "🔄 Đã tải lại menu!" if lang == "vi" else "🔄 Menu reloaded!")
        elif call.data.startswith("deposit_"):
            handle_deposit_amount(call)
        elif call.data.startswith("buy_"):
            handle_buy(call)
        elif call.data == "outofstock":
            lang = get_lang(call.from_user.id)
            bot.send_message(call.message.chat.id, 
                "❌ Sản phẩm hiện đang hết hàng!" if lang == "vi" else "❌ Product is out of stock!")
        elif call.data in ["confirm_reset_all", "cancel_reset_all"]:
            handle_reset_all(call)
        elif call.data.startswith("confirm_xoasoduall_"):
            handle_xoasoduall_callback(call)
        elif call.data == "cancel_xoasoduall":
            bot.edit_message_text("❌ Đã hủy thao tác xóa số dư.", call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id, "Đã hủy")
        elif call.data == "confirm_broadcast":
            handle_confirm_broadcast(call)
        elif call.data == "preview_broadcast":
            handle_preview_broadcast(call)
        elif call.data == "cancel_broadcast":
            handle_cancel_broadcast(call)
    except Exception as e:
        print("Lỗi callback:", e)

def handle_reset_all(call):
    if call.from_user.id != ADMIN_ID:
        return
    if call.data == "cancel_reset_all":
        bot.edit_message_text("Đã hủy.", call.message.chat.id, call.message.message_id)
        return
    users.update_many({}, {"$set": {"balance": 0, "balance_usdt": 0}})
    bot.edit_message_text("✅ Đã reset số dư về 0 cho tất cả user.", call.message.chat.id, call.message.message_id)

def handle_xoasoduall_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Bạn không có quyền!", show_alert=True)
        return
    
    currency = call.data.replace("confirm_xoasoduall_", "")
    
    total_users = users.count_documents({})
    total_vnd = sum(u.get('balance', 0) for u in users.find())
    total_usdt = sum(u.get('balance_usdt', 0) for u in users.find())
    
    if currency == "vnd":
        users.update_many({}, {"$set": {"balance": 0}})
        result_text = f"✅ **ĐÃ XÓA TOÀN BỘ SỐ DƯ VND**\n\n👥 Đã xử lý: **{total_users}** user\n💰 Đã xóa: **{total_vnd:,}đ**"
    elif currency == "usdt":
        users.update_many({}, {"$set": {"balance_usdt": 0}})
        result_text = f"✅ **ĐÃ XÓA TOÀN BỘ SỐ DƯ USDT**\n\n👥 Đã xử lý: **{total_users}** user\n💵 Đã xóa: **{total_usdt} USDT**"
    else:
        users.update_many({}, {"$set": {"balance": 0, "balance_usdt": 0}})
        result_text = f"✅ **ĐÃ XÓA TOÀN BỘ SỐ DƯ (VND + USDT)**\n\n👥 Đã xử lý: **{total_users}** user\n💰 Đã xóa VND: **{total_vnd:,}đ**\n💵 Đã xóa USDT: **{total_usdt} USDT**"
    
    bot.edit_message_text(result_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    bot.answer_callback_query(call.id, "✅ Đã xóa thành công!")

# ================== XỬ LÝ TIN NHẮN THÔNG THƯỜNG ==================
@bot.message_handler(func=lambda m: True)
def handle_user_message(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if message.text and message.text.startswith('/'):
        lang = user.get("language", "vi")
        if lang == "vi":
            bot.reply_to(message, "❌ Lệnh không tồn tại. Dùng /start để bắt đầu.")
        else:
            bot.reply_to(message, "❌ Command not found. Use /start to begin.")
        return
    
    waiting_for = user.get("waiting_email_for")
    
    if waiting_for:
        email = message.text.strip()
        lang = user.get("language", "vi")
        
        if not re.match(r'^[\w\.-]+@gmail\.com$', email, re.IGNORECASE):
            bot.reply_to(message, t(user_id, 'email_invalid'))
            return
        
        pending = orders.find_one({"order_code": waiting_for, "user_id": user_id, "status": "waiting_email"})
        
        if pending:
            category = pending.get('category')
            product_name = CATEGORIES.get(category, {}).get("name" if lang == "vi" else "name_en", "1 Slot")
            
            bot.send_message(ADMIN_ID, f"""
📨 **YÊU CẦU THÊM {product_name} / REQUEST FOR {product_name}**

Mã đơn/Order: #{pending['order_code']}
User ID: `{user_id}`
Tên/Name: {message.from_user.first_name or 'N/A'}
Email: `{email}`
Ngôn ngữ/Language: {lang.upper()}
            """)
            
            orders.update_one(
                {"_id": pending["_id"]}, 
                {"$set": {"status": "waiting_admin", "user_email": email}}
            )
            
            users.update_one(
                {"user_id": user_id}, 
                {"$set": {"waiting_email_for": None}}
            )
            
            bot.reply_to(message, t(user_id, 'email_sent'))
        else:
            users.update_one(
                {"user_id": user_id}, 
                {"$set": {"waiting_email_for": None}}
            )
            bot.reply_to(message, "❌ Không tìm thấy đơn hàng. Vui lòng dùng /start để bắt đầu lại.")
        
        return
    
    lang = user.get("language", "vi")
    if lang == "vi":
        bot.reply_to(message, "❌ Không hiểu lệnh. Dùng /start để bắt đầu.")
    else:
        bot.reply_to(message, "❌ Command not understood. Use /start to begin.")

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
    print(f"📊 Tỷ giá USDT: 1 USDT = {USDT_RATE:,}đ")
    print(f"👑 Admin Binance ID: {ADMIN_BINANCE_ID}")
    print(f"🆔 Admin Telegram ID: {ADMIN_ID}")
    bot.infinity_polling()
