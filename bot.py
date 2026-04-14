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

RATE_USDT_VND = 26340  # Tỷ giá USDT ≈ 26.340 VND (cập nhật khi cần)

CATEGORIES = {
    "hotspot": {"name": "Hotspot Shield 7D", "price_vnd": 2000},
    "gemini": {"name": "Gemini Pro 1 Acc 26-29D", "price_vnd": 40000},
    "capcut": {"name": "CapCut Pro 1 Tuần", "price_vnd": 2000},
    "canva1slot": {"name": "Canva 1 Slot", "price_vnd": 2000},
    "canva100slot": {"name": "Canva 100 Slot", "price_vnd": 30000},
    "youtube1slot": {"name": "YouTube 1 Slot", "price_vnd": 2000},
}

for code, info in CATEGORIES.items():
    categories.update_one({"code": code}, {"$setOnInsert": {
        "code": code, "name": info["name"], "price_vnd": info["price_vnd"], "enabled": True
    }}, upsert=True)

# ================== TRANSLATIONS ==================
TRANSLATIONS = {
    "vi": {
        "welcome": "👋 Chào **{name}**!\n\nChọn sản phẩm bạn muốn mua:",
        "choose_language": "🌐 Chọn ngôn ngữ / Choose language:",
        "wallet": "💰 Ví của tôi",
        "deposit": "💳 Nạp tiền vào ví",
        "language": "🌐 Ngôn ngữ",
        "out_of_stock": "🔒 Hết hàng",
        "stock_left": "(còn {count})",
        "buy_button": "🛒 Mua {name} - {price:,}đ {stock}",
        "no_stock": "❌ Sản phẩm đã hết hàng!",
        "product_not_exist": "❌ Sản phẩm không tồn tại!",
        "insufficient_balance": "❌ Số dư ví không đủ!\nCần {price:,}đ\nHiện có: {balance:,}đ",
        "email_prompt": "✅ Đã trừ {price:,}đ từ ví!\n\n📧 Vui lòng gửi **email (@gmail.com)** của bạn ngay bây giờ.",
        "email_invalid": "❌ Chỉ chấp nhận email @gmail.com!",
        "email_sent": "✅ Email đã được gửi cho admin!",
        "buy_success": "🎉 **Mua thành công từ ví!**\n\nSản phẩm: {name}\nTài khoản: {account}\nSố dư còn lại: {balance:,}đ",
        "purchase_pending": "✅ Đơn hàng #{order_code} đã tạo!\n\n💰 Số tiền: {price:,}đ\n📦 Sản phẩm: {name}\n\n🔗 [Thanh toán ngay]({url})",
    },
    "en": {
        "welcome": "👋 Hello **{name}**!\n\nChoose the product you want to buy:",
        "choose_language": "🌐 Choose language:",
        "wallet": "💰 My Wallet",
        "deposit": "💳 Deposit to wallet",
        "language": "🌐 Language",
        "out_of_stock": "🔒 Out of stock",
        "stock_left": "({count} left)",
        "buy_button": "🛒 Buy {name} - {price} USDT {stock}",
        "no_stock": "❌ Product is out of stock!",
        "product_not_exist": "❌ Product does not exist!",
        "insufficient_balance": "❌ Insufficient balance!\nRequired: {price} USDT\nCurrent: {balance} USDT",
        "email_prompt": "✅ Deducted {price} USDT from wallet!\n\n📧 Please send your **email (@gmail.com)** now.",
        "email_invalid": "❌ Only @gmail.com emails are accepted!",
        "email_sent": "✅ Email has been sent to admin!",
        "buy_success": "🎉 **Purchase successful from wallet!**\n\nProduct: {name}\nAccount: {account}\nRemaining balance: {balance} USDT",
        "purchase_pending": "✅ Order #{order_code} created!\n\n💰 Amount: {price} USDT\n📦 Product: {name}\n\n🔗 [Pay Now]({url})",
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

def get_user(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "username": None,
            "first_name": None,
            "balance": 0,
            "joined_at": datetime.now(),
            "language": "vi"
        }
        users.insert_one(user)
    elif "language" not in user:
        users.update_one({"user_id": user_id}, {"$set": {"language": "vi"}})
        user["language"] = "vi"
    return user

def update_balance(user_id, amount):
    users.update_one({"user_id": user_id}, {"$inc": {"balance": amount}})

def generate_order_code():
    return random.randint(10000000, 99999999)

def get_stock_count(category):
    stock_doc = stocks.find_one({"category": category})
    return len(stock_doc.get("accounts", [])) if stock_doc else 0

def get_price(lang, price_vnd):
    if lang == "en":
        return round(price_vnd / RATE_USDT_VND, 2)   # hiển thị USDT
    return price_vnd

# ================== /start ==================
@bot.message_handler(commands=['start'])
def start(message):
    user = get_user(message.from_user.id)
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(telebot.types.InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="set_lang_vi"))
    markup.add(telebot.types.InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en"))
    bot.send_message(message.chat.id, get_text(message.from_user.id, "choose_language"), reply_markup=markup)

# ================== CALLBACK HANDLER ==================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    try:
        if call.data.startswith("set_lang_"):
            lang = "vi" if call.data == "set_lang_vi" else "en"
            users.update_one({"user_id": call.from_user.id}, {"$set": {"language": lang}})
            show_main_menu(call.message.chat.id, call.from_user.id)
        
        elif call.data == "my_wallet":
            show_wallet(call)
        elif call.data == "deposit":
            deposit_menu(call)
        elif call.data.startswith("deposit_"):
            handle_deposit_amount(call)
        elif call.data.startswith("buy_"):
            handle_buy(call)
        elif call.data == "outofstock":
            bot.send_message(call.message.chat.id, get_text(call.from_user.id, "no_stock"))
        elif call.data in ["confirm_reset_all", "cancel_reset_all"]:
            handle_reset_all(call)
    except Exception as e:
        print("Lỗi callback:", e)

def show_main_menu(chat_id, user_id):
    user = get_user(user_id)
    lang = user.get("language", "vi")
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)

    for code, info in CATEGORIES.items():
        stock_count = get_stock_count(code)
        price = get_price(lang, info["price_vnd"])
        unit = "đ" if lang == "vi" else "USDT"

        if stock_count > 0:
            stock_text = get_text(user_id, "stock_left", count=stock_count) if lang == "vi" else get_text(user_id, "stock_left", count=stock_count)
            btn_text = get_text(user_id, "buy_button", name=info["name"], price=price, stock=stock_text)
            markup.add(telebot.types.InlineKeyboardButton(btn_text, callback_data=f"buy_{code}"))
        else:
            btn_text = f"{info['name']} - {get_text(user_id, 'out_of_stock')}"
            markup.add(telebot.types.InlineKeyboardButton(btn_text, callback_data="outofstock"))

    markup.add(telebot.types.InlineKeyboardButton(get_text(user_id, "wallet"), callback_data="my_wallet"))
    markup.add(telebot.types.InlineKeyboardButton(get_text(user_id, "deposit"), callback_data="deposit"))
    markup.add(telebot.types.InlineKeyboardButton(get_text(user_id, "language"), callback_data="change_language"))  # có thể thêm nếu muốn

    welcome = get_text(user_id, "welcome", name=bot.get_chat(user_id).first_name or "User")
    bot.send_message(chat_id, welcome, parse_mode='Markdown', reply_markup=markup)

def show_wallet(call):
    user = get_user(call.from_user.id)
    lang = user.get("language", "vi")
    balance = user.get('balance', 0)
    if lang == "en":
        balance_text = f"{round(balance / RATE_USDT_VND, 2)} USDT"
    else:
        balance_text = f"{balance:,}đ"

    text = f"""
🆔 **ID:** `{call.from_user.id}`
👤 **Name:** {call.from_user.first_name or 'No name'}
💰 **Balance:** {balance_text}
📅 **Joined:** {user.get('joined_at', datetime.now()).strftime('%d/%m/%Y')}
    """
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

# ================== ADMIN COMMANDS (ĐÃ FIX) ==================
@bot.message_handler(commands=['users', 'balance'])
def admin_view_balances(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    all_users = users.find().sort("balance", -1)
    text = "📊 **DANH SÁCH SỐ DƯ**\n\n"
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
        bot.send_message(order['user_id'], f"✅ Nạp tiền đã được duyệt!\n+{amount:,}đ\nSố dư: {get_user(order['user_id'])['balance']:,}đ")
        bot.reply_to(message, f"✅ Đã duyệt #{order_code} - Cộng {amount:,}đ")
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
            return bot.reply_to(message, "❌ Hết stock!")
        account = stock_doc["accounts"].pop(0)
        stocks.update_one({"category": category}, {"$set": {"accounts": stock_doc["accounts"]}})
        bot.send_message(order["user_id"], f"""
🎉 **Tài khoản đã được giao!**

Đơn: #{order_code}
Sản phẩm: {CATEGORIES.get(category, {}).get('name', category)}
Tài khoản: {account}
        """)
        orders.update_one({"order_code": order_code}, {"$set": {"status": "delivered", "delivered_at": datetime.now(), "account": account}})
        bot.reply_to(message, f"✅ Đã giao đơn #{order_code}")
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
        bot.reply_to(message, f"✅ Reset số dư user `{user_id}` về 0đ (từ {old:,}đ)")
    except:
        bot.reply_to(message, "Sử dụng: /resetbalance <user_id>")

@bot.message_handler(commands=['resetallbalance'])
def admin_reset_all_balance(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ Xác nhận", callback_data="confirm_reset_all"))
    markup.add(telebot.types.InlineKeyboardButton("❌ Hủy", callback_data="cancel_reset_all"))
    bot.reply_to(message, "⚠️ Reset số dư về 0 cho **TẤT CẢ** user?", reply_markup=markup)

def handle_reset_all(call):
    if call.from_user.id != ADMIN_ID:
        return
    if call.data == "cancel_reset_all":
        bot.edit_message_text("Đã hủy.", call.message.chat.id, call.message.message_id)
        return
    users.update_many({}, {"$set": {"balance": 0}})
    bot.edit_message_text("✅ Đã reset số dư tất cả user về 0đ.", call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['resetcanva1'])
def admin_reset_canva1(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    stocks.update_one({"category": "canva1slot"}, {"$set": {"accounts": ["Slot sẵn sàng"] * 100}}, upsert=True)
    bot.reply_to(message, "✅ Reset Canva 1 Slot về **100 slot**!")

@bot.message_handler(commands=['resetyoutube'])
def admin_reset_youtube(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    stocks.update_one({"category": "youtube1slot"}, {"$set": {"accounts": ["Slot sẵn sàng"] * 10}}, upsert=True)
    bot.reply_to(message, "✅ Reset YouTube 1 Slot về **10 slot**!")

# ================== Các hàm nạp tiền, mua hàng (giữ nguyên logic cũ, chỉ chỉnh ngôn ngữ) ==================
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
            bot.send_message(call.message.chat.id, get_text(call.from_user.id, "no_stock"))
        elif call.data == "change_language":
            change_language(call)
        elif call.data.startswith("set_lang_"):
            handle_set_language(call)
    except Exception as e:
        print("Lỗi callback:", e)

def show_wallet(call):
    user = get_user(call.from_user.id)
    joined = user.get('joined_at', datetime.now()).strftime('%d/%m/%Y')
    text = get_text(call.from_user.id, "wallet_info",
                    user_id=call.from_user.id,
                    name=call.from_user.first_name or 'Không có tên',
                    balance=user.get('balance', 0),
                    joined=joined)
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

def change_language(call):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="set_lang_vi"))
    markup.add(telebot.types.InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en"))
    bot.send_message(call.message.chat.id, get_text(call.from_user.id, "choose_language"), reply_markup=markup)

def handle_set_language(call):
    lang_code = "vi" if call.data == "set_lang_vi" else "en"
    users.update_one({"user_id": call.from_user.id}, {"$set": {"language": lang_code}})
    if lang_code == "vi":
        confirm = "✅ Ngôn ngữ đã được đặt thành Tiếng Việt!"
    else:
        confirm = "✅ Language has been set to English!"
    bot.send_message(call.message.chat.id, confirm)
    # User có thể gõ /start để xem menu mới

# ================== NẠP TIỀN (PayOS + Binance mới) ==================
def deposit_menu(call):
    user_id = call.from_user.id
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("50.000đ", callback_data="deposit_50000"))
    markup.add(telebot.types.InlineKeyboardButton("100.000đ", callback_data="deposit_100000"))
    markup.add(telebot.types.InlineKeyboardButton("200.000đ", callback_data="deposit_200000"))
    markup.add(telebot.types.InlineKeyboardButton(get_text(user_id, "deposit_custom"), callback_data="deposit_custom"))
    markup.add(telebot.types.InlineKeyboardButton(get_text(user_id, "deposit_binance"), callback_data="deposit_binance"))
    title = get_text(user_id, "deposit_menu")
    bot.send_message(call.message.chat.id, title, reply_markup=markup)

def handle_deposit_amount(call):
    if call.data == "deposit_custom":
        bot.send_message(call.message.chat.id, get_text(call.from_user.id, "custom_deposit_prompt"))
        bot.register_next_step_handler(call.message, process_custom_deposit)
        return
    elif call.data == "deposit_binance":
        bot.send_message(call.message.chat.id, get_text(call.from_user.id, "binance_deposit_prompt"))
        bot.register_next_step_handler(call.message, process_binance_deposit)
        return
    try:
        amount = int(call.data.split("_")[1])
        create_deposit_payment(call.message.chat.id, call.from_user.id, amount)
    except:
        bot.send_message(call.message.chat.id, "❌ Có lỗi khi xử lý.")

def process_custom_deposit(message):
    try:
        amount = int(message.text.strip())
        if amount < 2000:
            return bot.reply_to(message, get_text(message.from_user.id, "min_deposit_error"))
        create_deposit_payment(message.chat.id, message.from_user.id, amount)
    except ValueError:
        bot.reply_to(message, get_text(message.from_user.id, "invalid_amount"))
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

def process_binance_deposit(message):
    try:
        usdt_str = message.text.strip().replace(",", ".")
        usdt = float(usdt_str)
        if usdt < 1:
            return bot.reply_to(message, get_text(message.from_user.id, "binance_min_error"))
        vnd_amount = int(usdt * RATE_USDT_VND)
        create_binance_deposit(message.chat.id, message.from_user.id, usdt, vnd_amount)
    except ValueError:
        bot.reply_to(message, get_text(message.from_user.id, "invalid_amount"))
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

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

    text = get_text(user_id, "deposit_created", order_code=order_code, amount=amount, checkout_url=payment_link.checkout_url)
    bot.send_message(chat_id, text, parse_mode='Markdown')

def create_binance_deposit(chat_id, user_id, usdt, vnd_amount):
    order_code = generate_order_code()
    order = {
        "order_code": order_code,
        "user_id": user_id,
        "type": "deposit_binance",
        "amount": vnd_amount,
        "amount_usdt": usdt,
        "status": "pending",
        "created_at": datetime.now()
    }
    orders.insert_one(order)
    notify_admin(order)

    text = get_text(user_id, "binance_deposit_created", order_code=order_code, usdt=usdt, vnd=vnd_amount)
    bot.send_message(chat_id, text, parse_mode='Markdown')

# ================== MUA HÀNG & XỬ LÝ EMAIL ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    code = call.data.split("_")[1]
    info = CATEGORIES.get(code)
    if not info:
        return bot.send_message(call.message.chat.id, get_text(call.from_user.id, "product_not_exist"))

    user = get_user(call.from_user.id)
    price = info["price"]
    stock_count = get_stock_count(code)

    if stock_count <= 0:
        return bot.send_message(call.message.chat.id, get_text(call.from_user.id, "no_stock"))

    if code in ["canva1slot", "youtube1slot"]:
        if user.get("balance", 0) < price:
            return bot.send_message(call.message.chat.id, get_text(call.from_user.id, "insufficient_balance", price=price, balance=user.get('balance', 0)))

        update_balance(call.from_user.id, -price)
        order_code = generate_order_code()
        order = {
            "order_code": order_code,
            "user_id": call.from_user.id,
            "category": code,
            "amount": price,
            "type": code,
            "status": "waiting_email",
            "created_at": datetime.now()
        }
        orders.insert_one(order)
        notify_admin(order)

        stock_doc = stocks.find_one({"category": code})
        if stock_doc and stock_doc.get("accounts"):
            stock_doc["accounts"].pop(0)
            stocks.update_one({"category": code}, {"$set": {"accounts": stock_doc["accounts"]}})

        text = get_text(call.from_user.id, "email_prompt", price=price)
        bot.send_message(call.message.chat.id, text)
        return

    # Các sản phẩm khác
    if user.get("balance", 0) >= price:
        update_balance(call.from_user.id, -price)
        stock_doc = stocks.find_one({"category": code})
        if stock_doc and stock_doc.get("accounts"):
            account = stock_doc["accounts"].pop(0)
            stocks.update_one({"category": code}, {"$set": {"accounts": stock_doc["accounts"]}})
            user_after = get_user(call.from_user.id)  # refresh balance
            text = get_text(call.from_user.id, "buy_success_wallet", name=info['name'], account=account, balance=user_after.get('balance', 0))
            bot.send_message(call.message.chat.id, text)
    else:
        # Tạo đơn PayOS
        order_code = generate_order_code()
        order = {"order_code": order_code, "user_id": call.from_user.id, "category": code, "amount": price, "type": "purchase", "status": "pending", "created_at": datetime.now()}
        orders.insert_one(order)
        notify_admin(order)

        payment_data = CreatePaymentLinkRequest(
            order_code=order_code,
            amount=price,
            description=f"Don #{order_code}",
            return_url="https://t.me/" + bot.get_me().username,
            cancel_url="https://t.me/" + bot.get_me().username
        )
        payment_link = payos.payment_requests.create(payment_data)
        text = get_text(call.from_user.id, "purchase_pending", order_code=order_code, price=price, name=info['name'], checkout_url=payment_link.checkout_url)
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(func=lambda m: True)
def handle_user_message(message):
    pending = orders.find_one({"user_id": message.from_user.id, "status": "waiting_email"})
    if pending:
        email = message.text.strip()
        if not re.match(r'^[\w\.-]+@gmail\.com$', email, re.IGNORECASE):
            return bot.reply_to(message, get_text(message.from_user.id, "email_invalid"))
        
        bot.send_message(ADMIN_ID, f"""
📨 **YÊU CẦU THÊM {CATEGORIES.get(pending.get('category'), {}).get('name', '1 Slot')}**

Mã đơn: #{pending['order_code']}
User ID: `{message.from_user.id}`
Tên: {message.from_user.first_name or 'Không tên'}
Email: `{email}`
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
    print("🤖 Bot đang chạy... (Đã fix admin + menu ngôn ngữ + giá USDT khi chọn English)")
    bot.infinity_polling()
