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
ADMIN_BINANCE_ID = os.getenv('ADMIN_BINANCE_ID', '1163285604')  # ID Binance admin
USDT_RATE = int(os.getenv('USDT_RATE', 25000))  # 1 USDT = 25000 VND

users = db['users']
orders = db['orders']
stocks = db['stocks']
categories = db['categories']
transfers = db['transfers']  # Collection mới cho chuyển tiền Binance

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
        "choose_lang": "🌐 **Chọn ngôn ngữ / Choose language**",
        "lang_vi": "🇻🇳 Tiếng Việt",
        "lang_en": "🇬🇧 English",
        "wallet": "💰 Ví của tôi",
        "deposit": "💳 Nạp tiền vào ví",
        "transfer": "💸 Chuyển tiền Binance",
        "buy": "🛒 Mua {name} - {price}",
        "out_of_stock": "{name} - 🔒 Hết hàng",
        "balance": "💰 **Số dư:** `{balance:,}đ`",
        "insufficient": "❌ Số dư ví không đủ!\nCần {price:,}đ\nHiện có: {balance:,}đ",
        "insufficient_usdt": "❌ Insufficient balance!\nNeed {price} USDT\nCurrent: {balance} USDT",
        "transfer_prompt": "💸 Nhập ID Binance và số USDT muốn chuyển (tối thiểu 1 USDT):\nVí dụ: `1163285604 5`",
        "transfer_success": "✅ Đã gửi yêu cầu chuyển {amount} USDT đến ID Binance `{binance_id}`\nAdmin sẽ xác nhận sớm!",
        "transfer_error": "❌ Định dạng không đúng! Vui lòng nhập: `<ID_Binance> <số_USDT>`\nVí dụ: `1163285604 5`",
        "transfer_min": "❌ Số USDT tối thiểu là 1!",
    },
    "en": {
        "welcome": "👋 Hello **{name}**!\n\nChoose a product to buy:",
        "choose_lang": "🌐 **Choose language / Chọn ngôn ngữ**",
        "lang_vi": "🇻🇳 Vietnamese",
        "lang_en": "🇬🇧 English",
        "wallet": "💰 My Wallet",
        "deposit": "💳 Deposit to Wallet",
        "transfer": "💸 Binance Transfer",
        "buy": "🛒 Buy {name} - {price} USDT",
        "out_of_stock": "{name} - 🔒 Out of Stock",
        "balance": "💰 **Balance:** `{balance} USDT`",
        "insufficient": "❌ Insufficient balance!\nNeed {price} USDT\nCurrent: {balance} USDT",
        "insufficient_usdt": "❌ Insufficient balance!\nNeed {price} USDT\nCurrent: {balance} USDT",
        "transfer_prompt": "💸 Enter Binance ID and USDT amount (min 1 USDT):\nExample: `1163285604 5`",
        "transfer_success": "✅ Transfer request of {amount} USDT to Binance ID `{binance_id}` sent!\nAdmin will confirm soon!",
        "transfer_error": "❌ Invalid format! Please enter: `<Binance_ID> <USDT_amount>`\nExample: `1163285604 5`",
        "transfer_min": "❌ Minimum transfer amount is 1 USDT!",
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
            "balance_usdt": 0,  # Số dư USDT
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
    except:
        pass

def notify_admin_transfer(transfer_data):
    """Thông báo admin về yêu cầu chuyển tiền Binance"""
    user = get_user(transfer_data["user_id"])
    text = f"""
💸 **YÊU CẦU CHUYỂN TIỀN BINANCE / BINANCE TRANSFER REQUEST**

Mã yêu cầu/Request ID: #{transfer_data['transfer_code']}
User ID: `{transfer_data['user_id']}`
Tên/Name: {user.get('first_name', 'N/A')}
Binance ID người nhận/Recipient: `{transfer_data['binance_id']}`
Số USDT/Amount: **{transfer_data['amount_usdt']} USDT**
Trạng thái/Status: Chờ xác nhận/Pending

👉 Dùng lệnh /duyetchuyen {transfer_data['transfer_code']} để xác nhận
    """
    try:
        bot.send_message(ADMIN_ID, text, parse_mode='Markdown')
    except:
        pass

# ================== /start ==================
@bot.message_handler(commands=['start'])
def start(message):
    user = get_user(message.from_user.id)
    
    # Nếu chưa chọn ngôn ngữ, hiển thị menu chọn ngôn ngữ
    if not user.get("language"):
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            telebot.types.InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="lang_vi"),
            telebot.types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
        )
        bot.send_message(
            message.chat.id,
            "🌐 **Chọn ngôn ngữ / Choose language**\n\n"
            "Vui lòng chọn ngôn ngữ bạn muốn sử dụng.\n"
            "Please choose your preferred language.",
            parse_mode='Markdown',
            reply_markup=markup
        )
        return
    
    # Hiển thị menu chính theo ngôn ngữ đã chọn
    show_main_menu(message.chat.id, message.from_user.id, message.from_user.first_name)

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
            markup.add(telebot.types.InlineKeyboardButton(
                f"🛒 {t(user_id, 'buy', name=name, price=price_text)} (còn {stock_count})" if lang == "vi" 
                else f"🛒 {t(user_id, 'buy', name=name, price=price_text)} ({stock_count} left)",
                callback_data=f"buy_{code}"
            ))
        else:
            markup.add(telebot.types.InlineKeyboardButton(
                t(user_id, 'out_of_stock', name=name),
                callback_data="outofstock"
            ))
    
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'wallet'), callback_data="my_wallet"))
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'deposit'), callback_data="deposit"))
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, 'transfer'), callback_data="transfer_binance"))
    markup.add(telebot.types.InlineKeyboardButton("🌐 Đổi ngôn ngữ / Change Language", callback_data="change_language"))
    
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
        elif call.data == "transfer_binance":
            transfer_binance_prompt(call)
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
    lang = call.data.split("_")[1]  # 'vi' hoặc 'en'
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
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

# ================== CHUYỂN TIỀN BINANCE ==================
def transfer_binance_prompt(call):
    """Hiển thị hướng dẫn chuyển tiền Binance"""
    lang = get_lang(call.from_user.id)
    bot.send_message(
        call.message.chat.id,
        t(call.from_user.id, 'transfer_prompt'),
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(call.message, process_transfer_binance)

def process_transfer_binance(message):
    """Xử lý yêu cầu chuyển tiền Binance"""
    user_id = message.from_user.id
    lang = get_lang(user_id)
    
    try:
        # Parse input: <binance_id> <amount_usdt>
        parts = message.text.strip().split()
        if len(parts) != 2:
            return bot.reply_to(message, t(user_id, 'transfer_error'))
        
        binance_id = parts[0]
        amount_usdt = float(parts[1])
        
        if amount_usdt < 1:
            return bot.reply_to(message, t(user_id, 'transfer_min'))
        
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
        
        # Tạo order record để đồng bộ
        order = {
            "order_code": transfer_code,
            "user_id": user_id,
            "type": "transfer_binance",
            "binance_id": binance_id,
            "amount_usdt": amount_usdt,
            "amount": int(amount_usdt * USDT_RATE),  # Quy đổi ra VND để thống kê
            "status": "pending",
            "created_at": datetime.now()
        }
        orders.insert_one(order)
        
        # Thông báo cho admin
        notify_admin_transfer(transfer_data)
        
        # Gửi tin nhắn cho admin Binance
        bot.send_message(
            ADMIN_ID,
            f"💸 **YÊU CẦU CHUYỂN USDT**\n"
            f"Mã: #{transfer_code}\n"
            f"User: {user_id}\n"
            f"Binance ID: `{binance_id}`\n"
            f"Số USDT: **{amount_usdt}**\n\n"
            f"Dùng lệnh: `/duyetchuyen {transfer_code}` để xác nhận",
            parse_mode='Markdown'
        )
        
        bot.reply_to(
            message,
            t(user_id, 'transfer_success', amount=amount_usdt, binance_id=binance_id)
        )
        
    except ValueError:
        bot.reply_to(message, t(user_id, 'transfer_error'))
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi/Error: {str(e)}")

@bot.message_handler(commands=['duyetchuyen'])
def admin_duyet_chuyen(message):
    """Admin xác nhận chuyển tiền Binance"""
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được! / Admin only!")
    
    try:
        transfer_code = int(message.text.split()[1])
        transfer_data = transfers.find_one({"transfer_code": transfer_code, "status": "pending"})
        
        if not transfer_data:
            return bot.reply_to(message, "❌ Không tìm thấy yêu cầu chuyển tiền pending!")
        
        user_id = transfer_data['user_id']
        amount_usdt = transfer_data['amount_usdt']
        binance_id = transfer_data['binance_id']
        
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
            msg = f"✅ Yêu cầu chuyển {amount_usdt} USDT đến Binance ID `{binance_id}` đã được xác nhận!"
        else:
            msg = f"✅ Transfer request of {amount_usdt} USDT to Binance ID `{binance_id}` has been confirmed!"
        
        bot.send_message(user_id, msg, parse_mode='Markdown')
        bot.reply_to(message, f"✅ Đã duyệt chuyển tiền #{transfer_code} - {amount_usdt} USDT")
        
    except:
        bot.reply_to(message, "Sử dụng: /duyetchuyen <mã yêu cầu>")

@bot.message_handler(commands=['huy_chuyen'])
def admin_huy_chuyen(message):
    """Admin từ chối yêu cầu chuyển tiền Binance"""
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được! / Admin only!")
    
    try:
        parts = message.text.split(maxsplit=2)
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
        
    except:
        bot.reply_to(message, "Sử dụng: /huy_chuyen <mã yêu cầu> <lý do>")

# ================== NẠP TIỀN (ĐÃ SỬA) ==================
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
    msg = "💳 Chọn số tiền muốn nạp vào ví:" if lang == "vi" else "💳 Choose amount to deposit:"
    bot.send_message(call.message.chat.id, msg, reply_markup=markup)

def handle_deposit_amount(call):
    lang = get_lang(call.from_user.id)
    if call.data == "deposit_custom":
        msg = "Nhập số tiền muốn nạp (tối thiểu 2.000đ):" if lang == "vi" else "Enter deposit amount (min 2,000 VND):"
        bot.send_message(call.message.chat.id, msg)
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
    bot.send_message(chat_id, msg, parse_mode='Markdown')

# ================== MUA HÀNG & XỬ LÝ EMAIL ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
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
    else:
        price = info["price_usdt"]
        currency = "usdt"
        balance = user.get("balance_usdt", 0)

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
            "amount": info["price"],  # Lưu giá VND gốc
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

    # Các sản phẩm khác
    if balance >= price:
        update_balance(user_id, -price, currency)
        stock_doc = stocks.find_one({"category": code})
        if stock_doc and stock_doc.get("accounts"):
            account = stock_doc["accounts"].pop(0)
            stocks.update_one({"category": code}, {"$set": {"accounts": stock_doc["accounts"]}})
            
            product_name = info["name"] if lang == "vi" else info["name_en"]
            new_balance = balance - price
            if lang == "vi":
                msg = f"""
🎉 **Mua thành công từ ví!**

Sản phẩm: {product_name}
Tài khoản: {account}
Số dư còn lại: {new_balance:,}đ
                """
            else:
                msg = f"""
🎉 **Purchase successful!**

Product: {product_name}
Account: {account}
Remaining balance: {new_balance} USDT
                """
            bot.send_message(call.message.chat.id, msg)
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
        bot.send_message(call.message.chat.id, msg, parse_mode='Markdown')

# ================== ADMIN COMMANDS (Giữ nguyên) ==================
@bot.message_handler(commands=['users', 'balance'])
def admin_view_balances(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    all_users = users.find().sort("balance", -1)
    text = "📊 **DANH SÁCH SỐ DƯ USER**\n\n"
    for u in all_users:
        name = u.get('first_name') or u.get('username') or 'Unknown'
        lang = u.get('language', 'vi')
        text += f"👤 {name} (ID: `{u['user_id']}`) [{lang.upper()}] → 💰 `{u.get('balance', 0):,}đ` | 💵 `{u.get('balance_usdt', 0)} USDT`\n"
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
        
        user = get_user(user_id)
        lang = user.get("language", "vi")
        if lang == "vi":
            msg = f"✅ Nạp tiền đã được duyệt!\nSố tiền: +{amount:,}đ\nSố dư hiện tại: {get_user(user_id)['balance']:,}đ"
        else:
            msg = f"✅ Deposit approved!\nAmount: +{amount:,} VND\nCurrent balance: {get_user(user_id)['balance']:,} VND"
        
        bot.send_message(user_id, msg)
        bot.reply_to(message, f"✅ Đã duyệt nạp tiền #{order_code} - Cộng {amount:,}đ cho user {user_id}")
    except:
        bot.reply_to(message, "Sử dụng: /duyetnap <mã đơn>")

@bot.message_handler(commands=['giao'])
def admin_giao(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        order_code = int(message.text.split()[1])
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
Tài khoản: {account}
            """
        else:
            msg = f"""
🎉 **Account delivered!**

Order: #{order_code}
Product: {product_name}
Account: {account}
            """
        bot.send_message(user_id, msg)
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
        new_rate = int(message.text.split()[1])
        USDT_RATE = new_rate
        bot.reply_to(message, f"✅ Đã cập nhật tỷ giá: 1 USDT = {new_rate:,}đ")
    except:
        bot.reply_to(message, "Sử dụng: /setusdtrate <tỷ_giá>\nVí dụ: /setusdtrate 25000")

@bot.message_handler(commands=['addbalance'])
def admin_add_balance(message):
    """Admin cộng tiền cho user"""
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        amount = int(parts[2])
        currency = parts[3] if len(parts) > 3 else "vnd"
        
        update_balance(user_id, amount, currency)
        bot.reply_to(message, f"✅ Đã cộng {amount} {currency.upper()} cho user {user_id}")
    except:
        bot.reply_to(message, "Sử dụng: /addbalance <user_id> <số_tiền> [vnd|usdt]")

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
    bot.infinity_polling()
