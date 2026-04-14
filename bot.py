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
ADMIN_BINANCE_ID = os.getenv('ADMIN_BINANCE_ID', '1163285604')
USDT_RATE = int(os.getenv('USDT_RATE', 27000))  # 1 USDT = 27000 VND

users = db['users']
orders = db['orders']
stocks = db['stocks']
categories = db['categories']
transfers = db['transfers']

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
    categories.update_one({"code": code}, {"$setOnInsert": {
        "code": code, "name": info["name"], "name_en": info["name_en"], 
        "price": info["price"], "price_usdt": info["price_usdt"], 
        "type": info.get("type"), "enabled": True
    }}, upsert=True)

# ================== LANGUAGE SYSTEM ==================
LANGUAGES = {
    "vi": {
        "welcome": "👋 Chào **{name}**!\n\nChọn sản phẩm bạn muốn mua:",
        "choose_lang": "🌐 **Chọn ngôn ngữ / Choose language**\n\nVui lòng chọn ngôn ngữ bạn muốn sử dụng.",
        "lang_vi": "🇻🇳 Tiếng Việt",
        "lang_en": "🇬🇧 English",
        "wallet": "💰 Ví của tôi",
        "deposit": "💳 Nạp tiền vào ví",
        "deposit_usdt": "💵 Nạp USDT qua Binance",
        "transfer": "💸 Chuyển tiền Binance",
        "buy": "🛒 Mua {name} - {price}",
        "out_of_stock": "{name} - 🔒 Hết hàng",
        "balance": "💰 **Số dư:** `{balance:,}đ`",
        "insufficient": "❌ Số dư ví không đủ!\nCần {price:,}đ\nHiện có: {balance:,}đ",
        "insufficient_usdt": "❌ Số dư USDT không đủ!\nCần {price} USDT\nHiện có: {balance} USDT",
        "transfer_prompt": "💸 Nhập ID Binance và số USDT muốn chuyển (tối thiểu 1 USDT):\nVí dụ: `1163285604 5`",
        "transfer_success": "✅ Đã gửi yêu cầu chuyển {amount} USDT đến ID Binance `{binance_id}`\nAdmin sẽ xác nhận sớm!",
        "transfer_error": "❌ Định dạng không đúng! Vui lòng nhập: `<ID_Binance> <số_USDT>`\nVí dụ: `1163285604 5`",
        "transfer_min": "❌ Số USDT tối thiểu là 1!",
        "deposit_usdt_prompt": "💵 Nhập số USDT muốn nạp (tối thiểu 1 USDT):",
        "deposit_usdt_min": "❌ Số USDT tối thiểu là 1!",
        "deposit_usdt_invalid": "❌ Vui lòng nhập số hợp lệ!",
        "change_lang": "🌐 Đổi ngôn ngữ / Change Language",
        "back_to_menu": "🔙 Quay lại menu chính",
    },
    "en": {
        "welcome": "👋 Hello **{name}**!\n\nChoose a product to buy:",
        "choose_lang": "🌐 **Choose language / Chọn ngôn ngữ**\n\nPlease choose your preferred language.",
        "lang_vi": "🇻🇳 Vietnamese",
        "lang_en": "🇬🇧 English",
        "wallet": "💰 My Wallet",
        "deposit": "💳 Deposit VND",
        "deposit_usdt": "💵 Deposit USDT via Binance",
        "transfer": "💸 Binance Transfer",
        "buy": "🛒 Buy {name} - {price} USDT",
        "out_of_stock": "{name} - 🔒 Out of Stock",
        "balance": "💰 **Balance:** `{balance} USDT`",
        "insufficient": "❌ Insufficient balance!\nNeed {price} USDT\nCurrent: {balance} USDT",
        "insufficient_usdt": "❌ Insufficient USDT balance!\nNeed {price} USDT\nCurrent: {balance} USDT",
        "transfer_prompt": "💸 Enter Binance ID and USDT amount (min 1 USDT):\nExample: `1163285604 5`",
        "transfer_success": "✅ Transfer request of {amount} USDT to Binance ID `{binance_id}` sent!\nAdmin will confirm soon!",
        "transfer_error": "❌ Invalid format! Please enter: `<Binance_ID> <USDT_amount>`\nExample: `1163285604 5`",
        "transfer_min": "❌ Minimum transfer amount is 1 USDT!",
        "deposit_usdt_prompt": "💵 Enter the USDT amount to deposit (minimum 1 USDT):",
        "deposit_usdt_min": "❌ Minimum deposit is 1 USDT!",
        "deposit_usdt_invalid": "❌ Please enter a valid number!",
        "change_lang": "🌐 Change Language / Đổi ngôn ngữ",
        "back_to_menu": "🔙 Back to main menu",
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
            "joined_at": datetime.now()
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
    elif order["type"] == "transfer_binance":
        text = f"""
💸 **YÊU CẦU CHUYỂN TIỀN BINANCE**
Mã/Code: #{order['order_code']}
User ID: `{order['user_id']}`
Tên/Name: {user.get('first_name', 'N/A')}
Binance ID: `{order.get('binance_id', 'N/A')}`
Số USDT: **{order.get('amount_usdt', 0)} USDT**
Trạng thái/Status: Chờ xác nhận/Pending
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
    
    # Luôn hiển thị menu chọn ngôn ngữ trước
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
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'transfer'), callback_data="transfer_binance"))
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'change_lang'), callback_data="change_language"))
    
    bot.send_message(
        chat_id,
        t(user_id, 'welcome', name=first_name),
        parse_mode='Markdown',
        reply_markup=markup
    )

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
        elif call.data == "transfer_binance":
            transfer_binance_prompt(call)
        elif call.data == "back_to_menu":
            show_main_menu(call.message.chat.id, call.from_user.id, call.from_user.first_name)
        elif call.data.startswith("deposit_"):
            handle_deposit_amount(call)
        elif call.data.startswith("buy_"):
            handle_buy(call)
        elif call.data == "outofstock":
            lang = get_lang(call.from_user.id)
            bot.send_message(call.message.chat.id, 
                "❌ Sản phẩm hiện đang hết hàng!" if lang == "vi" else "❌ Product is out of stock!")
    except Exception as e:
        print("Lỗi callback:", e)

def handle_language_selection(call):
    """Xử lý khi người dùng chọn ngôn ngữ"""
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
    """Hiển thị menu đổi ngôn ngữ"""
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
    """Hiển thị prompt nhập số USDT muốn nạp"""
    lang = get_lang(call.from_user.id)
    msg = t(call.from_user.id, 'deposit_usdt_prompt')
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(t(call.from_user.id, 'back_to_menu'), callback_data="back_to_menu"))
    
    bot.send_message(call.message.chat.id, msg, reply_markup=markup)
    bot.register_next_step_handler(call.message, process_deposit_usdt)

def process_deposit_usdt(message):
    """Xử lý số USDT người dùng nhập và tạo hướng dẫn thanh toán"""
    user_id = message.from_user.id
    lang = get_lang(user_id)
    
    # Kiểm tra nếu người dùng muốn quay lại
    if message.text in ["/start", "/menu", "Quay lại", "Back"]:
        show_main_menu(message.chat.id, user_id, message.from_user.first_name)
        return
    
    try:
        amount_usdt = float(message.text.strip())
        
        if amount_usdt < 1:
            bot.reply_to(message, t(user_id, 'deposit_usdt_min'))
            bot.register_next_step_handler(message, process_deposit_usdt)
            return
        
        # Tạo đơn nạp USDT
        order_code = generate_order_code()
        amount_vnd = int(amount_usdt * USDT_RATE)
        
        order = {
            "order_code": order_code,
            "user_id": user_id,
            "type": "deposit_usdt",
            "amount_usdt": amount_usdt,
            "amount_vnd": amount_vnd,
            "amount": amount_vnd,  # Tương đương VND
            "status": "pending",
            "binance_id": ADMIN_BINANCE_ID,
            "created_at": datetime.now()
        }
        orders.insert_one(order)
        
        # Thông báo cho admin
        notify_admin(order)
        
        # Gửi hướng dẫn thanh toán cho user
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

# ================== CHUYỂN TIỀN BINANCE ==================
def transfer_binance_prompt(call):
    """Hiển thị hướng dẫn chuyển tiền Binance"""
    lang = get_lang(call.from_user.id)
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(t(call.from_user.id, 'back_to_menu'), callback_data="back_to_menu"))
    
    bot.send_message(
        call.message.chat.id,
        t(call.from_user.id, 'transfer_prompt'),
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.register_next_step_handler(call.message, process_transfer_binance)

def process_transfer_binance(message):
    """Xử lý yêu cầu chuyển tiền Binance"""
    user_id = message.from_user.id
    lang = get_lang(user_id)
    
    if message.text in ["/start", "/menu", "Quay lại", "Back"]:
        show_main_menu(message.chat.id, user_id, message.from_user.first_name)
        return
    
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            return bot.reply_to(message, t(user_id, 'transfer_error'))
        
        binance_id = parts[0]
        amount_usdt = float(parts[1])
        
        if amount_usdt < 1:
            return bot.reply_to(message, t(user_id, 'transfer_min'))
        
        # Kiểm tra số dư USDT
        user = get_user(user_id)
        if user.get('balance_usdt', 0) < amount_usdt:
            if lang == "vi":
                return bot.reply_to(message, f"❌ Số dư USDT không đủ!\nCần: {amount_usdt} USDT\nHiện có: {user.get('balance_usdt', 0)} USDT")
            else:
                return bot.reply_to(message, f"❌ Insufficient USDT balance!\nNeed: {amount_usdt} USDT\nCurrent: {user.get('balance_usdt', 0)} USDT")
        
        # Tạo mã chuyển tiền
        transfer_code = generate_order_code()
        
        transfer_data = {
            "transfer_code": transfer_code,
            "user_id": user_id,
            "binance_id": binance_id,
            "amount_usdt": amount_usdt,
            "status": "pending",
            "created_at": datetime.now()
        }
        transfers.insert_one(transfer_data)
        
        # Tạo order record
        order = {
            "order_code": transfer_code,
            "user_id": user_id,
            "type": "transfer_binance",
            "binance_id": binance_id,
            "amount_usdt": amount_usdt,
            "amount": int(amount_usdt * USDT_RATE),
            "status": "pending",
            "created_at": datetime.now()
        }
        orders.insert_one(order)
        
        # Thông báo cho admin
        notify_admin(order)
        
        bot.reply_to(
            message,
            t(user_id, 'transfer_success', amount=amount_usdt, binance_id=binance_id)
        )
        
    except ValueError:
        bot.reply_to(message, t(user_id, 'transfer_error'))

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

    # Xác định giá theo ngôn ngữ
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

    if code in ["canva1slot", "youtube1slot"]:
        if balance < price:
            if lang == "vi":
                msg = f"❌ Số dư ví không đủ!\nCần {price:,}đ\nHiện có: {balance:,}đ"
            else:
                msg = f"❌ Insufficient balance!\nNeed {price} USDT\nCurrent: {balance} USDT"
            return bot.send_message(call.message.chat.id, msg)

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

        if lang == "vi":
            msg = f"""
✅ Đã trừ {price:,}đ từ ví!

📧 Vui lòng gửi **email (@gmail.com)** của bạn ngay bây giờ.
            """
        else:
            msg = f"""
✅ Deducted {price} USDT from wallet!

📧 Please send your **email (@gmail.com)** now.
            """
        bot.send_message(call.message.chat.id, msg)
        return

    # Các sản phẩm khác - mua trực tiếp từ số dư
    if balance >= price:
        update_balance(user_id, -price, currency)
        stock_doc = stocks.find_one({"category": code})
        if stock_doc and stock_doc.get("accounts"):
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
🎉 **Mua thành công từ ví!**

Sản phẩm: {product_name}
Tài khoản: `{account}`
Số dư còn lại: {new_balance:,}đ
                """
            else:
                msg = f"""
🎉 **Purchase successful!**

Product: {product_name}
Account: `{account}`
Remaining balance: {new_balance} USDT
                """
            
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'back_to_menu'), callback_data="back_to_menu"))
            
            bot.send_message(call.message.chat.id, msg, parse_mode='Markdown', reply_markup=markup)
    else:
        # Tạo đơn PayOS cho sản phẩm thường
        order_code = generate_order_code()
        order = {
            "order_code": order_code, 
            "user_id": user_id, 
            "category": code, 
            "amount": info["price"], 
            "amount_usdt": info["price_usdt"],
            "type": "purchase", 
            "currency_used": currency,
            "status": "pending", 
            "created_at": datetime.now()
        }
        orders.insert_one(order)
        notify_admin(order)

        payment_data = CreatePaymentLinkRequest(
            order_code=order_code,
            amount=info["price"],
            description=f"Don #{order_code}",
            return_url="https://t.me/" + bot.get_me().username,
            cancel_url="https://t.me/" + bot.get_me().username
        )
        payment_link = payos.payment_requests.create(payment_data)
        
        product_name = info["name"] if lang == "vi" else info["name_en"]
        if lang == "vi":
            msg = f"""
✅ Đơn hàng #{order_code} đã tạo!

💰 Số tiền: {info['price']:,}đ
📦 Sản phẩm: {product_name}

🔗 [Thanh toán ngay]({payment_link.checkout_url})
            """
        else:
            msg = f"""
✅ Order #{order_code} created!

💰 Amount: {info['price']:,} VND
📦 Product: {product_name}

🔗 [Pay now]({payment_link.checkout_url})
            """
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'back_to_menu'), callback_data="back_to_menu"))
        
        bot.send_message(call.message.chat.id, msg, parse_mode='Markdown', reply_markup=markup)

# ================== ADMIN COMMANDS ==================
@bot.message_handler(commands=['admin'])
def admin_help(message):
    """Hiển thị danh sách lệnh admin"""
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    
    help_text = """
🔧 **ADMIN COMMANDS**

📊 **Quản lý user:**
/users - Xem danh sách số dư
/resetbalance <user_id> - Reset số dư 1 user
/resetallbalance - Reset tất cả số dư
/addbalance <user_id> <số> [vnd|usdt] - Cộng tiền

💰 **Quản lý nạp/rút:**
/duyetnap <mã> - Duyệt nạp VND
/duyetnapusdt <mã> - Duyệt nạp USDT
/duyetchuyen <mã> - Duyệt chuyển Binance
/huy_chuyen <mã> <lý do> - Từ chối chuyển

📦 **Quản lý đơn hàng:**
/giao <mã> - Giao tài khoản
/resetcanva1 - Reset Canva 1 Slot
/resetyoutube - Reset YouTube 1 Slot

⚙️ **Cài đặt:**
/setusdtrate <tỷ_giá> - Cập nhật tỷ giá USDT
    """
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['users'])
def admin_view_balances(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    
    all_users = users.find().sort("balance", -1)
    text = "📊 **DANH SÁCH SỐ DƯ USER**\n\n"
    
    for u in all_users:
        name = u.get('first_name') or u.get('username') or 'Unknown'
        lang = u.get('language', 'vi')
        balance_vnd = u.get('balance', 0)
        balance_usdt = u.get('balance_usdt', 0)
        text += f"👤 {name} (ID: `{u['user_id']}`) [{lang.upper()}]\n"
        text += f"   💰 VND: `{balance_vnd:,}đ` | 💵 USDT: `{balance_usdt}`\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['duyetnap'])
def admin_duyet_nap(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        parts = message.text.split()
        if len(parts) < 2:
            return bot.reply_to(message, "Sử dụng: /duyetnap <mã đơn>")
        
        order_code = int(parts[1])
        order = orders.find_one({"order_code": order_code, "type": "deposit", "status": "pending"})
        if not order:
            return bot.reply_to(message, "❌ Không tìm thấy đơn nạp pending!")
        
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
    """Admin duyệt nạp USDT"""
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        parts = message.text.split()
        if len(parts) < 2:
            return bot.reply_to(message, "Sử dụng: /duyetnapusdt <mã đơn>")
        
        order_code = int(parts[1])
        order = orders.find_one({"order_code": order_code, "type": "deposit_usdt", "status": "pending"})
        if not order:
            return bot.reply_to(message, "❌ Không tìm thấy đơn nạp USDT pending!")
        
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

@bot.message_handler(commands=['duyetchuyen'])
def admin_duyet_chuyen(message):
    """Admin xác nhận chuyển tiền Binance"""
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            return bot.reply_to(message, "Sử dụng: /duyetchuyen <mã yêu cầu>")
        
        transfer_code = int(parts[1])
        transfer_data = transfers.find_one({"transfer_code": transfer_code, "status": "pending"})
        
        if not transfer_data:
            return bot.reply_to(message, "❌ Không tìm thấy yêu cầu chuyển tiền pending!")
        
        user_id = transfer_data['user_id']
        amount_usdt = transfer_data['amount_usdt']
        binance_id = transfer_data['binance_id']
        
        # Trừ USDT từ tài khoản user
        user = get_user(user_id)
        if user.get('balance_usdt', 0) < amount_usdt:
            return bot.reply_to(message, f"❌ User không đủ USDT! Hiện có: {user.get('balance_usdt', 0)} USDT")
        
        update_balance(user_id, -amount_usdt, "usdt")
        
        # Cập nhật trạng thái
        transfers.update_one(
            {"transfer_code": transfer_code},
            {"$set": {"status": "completed", "approved_at": datetime.now(), "approved_by": ADMIN_ID}}
        )
        orders.update_one(
            {"order_code": transfer_code, "type": "transfer_binance"},
            {"$set": {"status": "completed"}}
        )
        
        # Thông báo cho user
        user_lang = get_lang(user_id)
        if user_lang == "vi":
            msg = f"✅ Yêu cầu chuyển {amount_usdt} USDT đến Binance ID `{binance_id}` đã được xác nhận và thực hiện!"
        else:
            msg = f"✅ Transfer request of {amount_usdt} USDT to Binance ID `{binance_id}` has been confirmed and executed!"
        
        bot.send_message(user_id, msg, parse_mode='Markdown')
        bot.reply_to(message, f"✅ Đã duyệt chuyển tiền #{transfer_code} - {amount_usdt} USDT")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /duyetchuyen <mã yêu cầu>")

@bot.message_handler(commands=['huy_chuyen'])
def admin_huy_chuyen(message):
    """Admin từ chối yêu cầu chuyển tiền Binance"""
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            return bot.reply_to(message, "Sử dụng: /huy_chuyen <mã yêu cầu> <lý do>")
        
        transfer_code = int(parts[1])
        reason = parts[2] if len(parts) > 2 else "Không có lý do / No reason provided"
        
        transfer_data = transfers.find_one({"transfer_code": transfer_code, "status": "pending"})
        
        if not transfer_data:
            return bot.reply_to(message, "❌ Không tìm thấy yêu cầu chuyển tiền pending!")
        
        transfers.update_one(
            {"transfer_code": transfer_code},
            {"$set": {"status": "rejected", "rejected_at": datetime.now(), "reason": reason}}
        )
        orders.update_one(
            {"order_code": transfer_code, "type": "transfer_binance"},
            {"$set": {"status": "rejected"}}
        )
        
        user_id = transfer_data['user_id']
        user_lang = get_lang(user_id)
        
        if user_lang == "vi":
            msg = f"❌ Yêu cầu chuyển tiền #{transfer_code} đã bị từ chối.\nLý do: {reason}"
        else:
            msg = f"❌ Transfer request #{transfer_code} has been rejected.\nReason: {reason}"
        
        bot.send_message(user_id, msg)
        bot.reply_to(message, f"✅ Đã từ chối chuyển tiền #{transfer_code}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /huy_chuyen <mã yêu cầu> <lý do>")

@bot.message_handler(commands=['giao'])
def admin_giao(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        parts = message.text.split()
        if len(parts) < 2:
            return bot.reply_to(message, "Sử dụng: /giao <mã đơn>")
        
        order_code = int(parts[1])
        order = orders.find_one({"order_code": order_code})
        if not order:
            return bot.reply_to(message, "❌ Không tìm thấy đơn!")
        
        category = order.get("category")
        user_id = order["user_id"]
        stock_doc = stocks.find_one({"category": category})
        
        if not stock_doc or not stock_doc.get("accounts"):
            return bot.reply_to(message, "❌ Hết stock loại này!")
        
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

@bot.message_handler(commands=['resetbalance'])
def admin_reset_balance(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        parts = message.text.split()
        if len(parts) < 2:
            return bot.reply_to(message, "Sử dụng: /resetbalance <user_id>")
        
        user_id = int(parts[1])
        old_vnd = get_user(user_id)['balance']
        old_usdt = get_user(user_id)['balance_usdt']
        update_balance(user_id, -old_vnd, "vnd")
        update_balance(user_id, -old_usdt, "usdt")
        bot.reply_to(message, f"✅ Đã reset số dư user `{user_id}`:\n- VND: {old_vnd:,}đ → 0đ\n- USDT: {old_usdt} → 0")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /resetbalance <user_id>")

@bot.message_handler(commands=['addbalance'])
def admin_add_balance(message):
    """Admin cộng tiền cho user"""
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        parts = message.text.split()
        if len(parts) < 3:
            return bot.reply_to(message, "Sử dụng: /addbalance <user_id> <số_tiền> [vnd|usdt]")
        
        user_id = int(parts[1])
        amount = float(parts[2]) if '.' in parts[2] else int(parts[2])
        currency = parts[3].lower() if len(parts) > 3 else "vnd"
        
        if currency not in ["vnd", "usdt"]:
            return bot.reply_to(message, "Currency phải là 'vnd' hoặc 'usdt'")
        
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
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ Xác nhận reset tất cả", callback_data="confirm_reset_all"))
    markup.add(telebot.types.InlineKeyboardButton("❌ Hủy", callback_data="cancel_reset_all"))
    bot.reply_to(message, "⚠️ Bạn sắp reset số dư về 0 cho **TẤT CẢ** user (cả VND và USDT). Xác nhận?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_reset_all", "cancel_reset_all"])
def handle_reset_all(call):
    if call.from_user.id != ADMIN_ID:
        return
    if call.data == "cancel_reset_all":
        bot.edit_message_text("Đã hủy.", call.message.chat.id, call.message.message_id)
        return
    users.update_many({}, {"$set": {"balance": 0, "balance_usdt": 0}})
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

@bot.message_handler(commands=['setusdtrate'])
def admin_set_usdt_rate(message):
    """Admin cập nhật tỷ giá USDT"""
    global USDT_RATE
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        parts = message.text.split()
        if len(parts) < 2:
            return bot.reply_to(message, "Sử dụng: /setusdtrate <tỷ_giá>")
        
        new_rate = int(parts[1])
        USDT_RATE = new_rate
        bot.reply_to(message, f"✅ Đã cập nhật tỷ giá: 1 USDT = {new_rate:,}đ")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /setusdtrate <tỷ_giá>")

# ================== XỬ LÝ TIN NHẮN THÔNG THƯỜNG ==================
@bot.message_handler(func=lambda m: True)
def handle_user_message(message):
    """Xử lý tin nhắn thông thường"""
    user_id = message.from_user.id
    
    # Kiểm tra nếu đang chờ email cho Canva/Youtube
    pending = orders.find_one({"user_id": user_id, "status": "waiting_email"})
    if pending:
        email = message.text.strip()
        if not re.match(r'^[\w\.-]+@gmail\.com$', email, re.IGNORECASE):
            lang = get_lang(user_id)
            msg = "❌ Chỉ chấp nhận email @gmail.com!" if lang == "vi" else "❌ Only @gmail.com emails are accepted!"
            return bot.reply_to(message, msg)
        
        user = get_user(user_id)
        lang = user.get("language", "vi")
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
        orders.update_one({"_id": pending["_id"]}, {"$set": {"status": "waiting_admin", "user_email": email}})
        
        if lang == "vi":
            msg = "✅ Email đã được gửi cho admin!"
        else:
            msg = "✅ Email has been sent to admin!"
        bot.reply_to(message, msg)
        return
    
    # Tin nhắn không xác định
    lang = get_lang(user_id)
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
    bot.infinity_polling()
