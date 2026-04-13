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
BINANCE_ADMIN_ID = "1163285604"   # Binance User ID nhận USDT

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
    "youtube1slot": {"name": "YouTube 1 Slot", "price": 2000, "type": "youtube_1slot"},
}

for code, info in CATEGORIES.items():
    categories.update_one({"code": code}, {"$setOnInsert": {
        "code": code, "name": info["name"], "price": info["price"], "type": info.get("type"), "enabled": True
    }}, upsert=True)

def get_user(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "username": None,
            "first_name": None,
            "balance": 0,
            "language": "vi",
            "joined_at": datetime.now()
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

# ================== TEXT THEO NGÔN NGỮ ==================
def t(user_id, key):
    user = get_user(user_id)
    lang = user.get("language", "vi")
    texts = {
        "welcome": {"vi": "👋 Chào **{name}**!\n\nChọn ngôn ngữ / Select language:", 
                    "en": "👋 Hello **{name}**!\n\nChoose language:"},
        "menu_title": {"vi": "Chọn sản phẩm bạn muốn mua:", 
                       "en": "Choose the product you want to buy:"},
        "my_wallet": {"vi": "💰 Ví của tôi", "en": "💰 My Wallet"},
        "deposit_vnd": {"vi": "💳 Nạp tiền VND (PayOS)", "en": "💳 Deposit VND (PayOS)"},
        "deposit_usdt": {"vi": "₮ Nạp USDT qua Binance", "en": "₮ Deposit USDT via Binance"},
        "out_of_stock": {"vi": "🔒 Hết hàng", "en": "🔒 Out of stock"},
        "buy_button": {"vi": "🛒 Mua {name} - {price:,}đ (còn {stock})", 
                       "en": "🛒 Buy {name} - ${price_usd:.1f} (stock: {stock})"}
    }
    return texts.get(key, {}).get(lang, key)

# ================== /START - CHỌN NGÔN NGỮ ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="lang_vi"),
        telebot.types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    bot.send_message(
        message.chat.id,
        t(message.from_user.id, "welcome").format(name=message.from_user.first_name),
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def set_language(call):
    bot.answer_callback_query(call.id)
    lang = "vi" if call.data == "lang_vi" else "en"
    users.update_one({"user_id": call.from_user.id}, {"$set": {"language": lang}})
    show_main_menu(call.message.chat.id, call.from_user.id)

def show_main_menu(chat_id, user_id):
    user = get_user(user_id)
    lang = user.get("language", "vi")
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    
    for code, info in CATEGORIES.items():
        stock_count = get_stock_count(code)
        if stock_count > 0:
            if lang == "vi":
                btn_text = f"🛒 Mua {info['name']} - {info['price']:,}đ (còn {stock_count})"
            else:
                btn_text = f"🛒 Buy {info['name']} - ${info['price']/23000:.1f} (stock: {stock_count})"
            markup.add(telebot.types.InlineKeyboardButton(btn_text, callback_data=f"buy_{code}"))
        else:
            out_text = f"{info['name']} - {t(user_id, 'out_of_stock')}"
            markup.add(telebot.types.InlineKeyboardButton(out_text, callback_data="outofstock"))
    
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, "my_wallet"), callback_data="my_wallet"))
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, "deposit_vnd"), callback_data="deposit_vnd"))
    markup.add(telebot.types.InlineKeyboardButton(t(user_id, "deposit_usdt"), callback_data="deposit_usdt"))
    
    bot.send_message(chat_id, t(user_id, "menu_title"), parse_mode='Markdown', reply_markup=markup)

# ================== CALLBACK HANDLER ==================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    data = call.data

    if data == "my_wallet":
        show_wallet(call)
    elif data == "deposit_vnd":
        deposit_vnd_menu(call)
    elif data == "deposit_usdt":
        deposit_usdt(call)
    elif data.startswith("deposit_") and data != "deposit_usdt":
        handle_deposit_amount(call)
    elif data.startswith("buy_"):
        handle_buy(call)
    elif data == "outofstock":
        bot.send_message(call.message.chat.id, "❌ Sản phẩm hiện đang hết hàng!" if get_user(call.from_user.id).get("language") == "vi" else "❌ Product is out of stock!")

def show_wallet(call):
    user = get_user(call.from_user.id)
    lang = user.get("language", "vi")
    joined = user.get('joined_at', datetime.now()).strftime('%d/%m/%Y')
    text = f"""
🆔 **ID:** `{call.from_user.id}`
👤 **Name:** {call.from_user.first_name or 'No name'}
💰 **Balance:** `{user.get('balance', 0):,}đ`
📅 **Joined:** {joined}
    """ if lang == "vi" else f"""
🆔 **ID:** `{call.from_user.id}`
👤 **Name:** {call.from_user.first_name or 'No name'}
💰 **Balance:** `${user.get('balance', 0)/23000:.1f}`
📅 **Joined:** {joined}
    """
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

# ================== NẠP VND (PayOS) ==================
def deposit_vnd_menu(call):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("50.000đ", callback_data="deposit_50000"))
    markup.add(telebot.types.InlineKeyboardButton("100.000đ", callback_data="deposit_100000"))
    markup.add(telebot.types.InlineKeyboardButton("200.000đ", callback_data="deposit_200000"))
    markup.add(telebot.types.InlineKeyboardButton("Nhập số khác" if get_user(call.from_user.id).get("language")=="vi" else "Custom amount", callback_data="deposit_custom"))
    bot.send_message(call.message.chat.id, "💳 Chọn số tiền muốn nạp:" if get_user(call.from_user.id).get("language")=="vi" else "💳 Choose deposit amount:", reply_markup=markup)

# ================== NẠP USDT QUA BINANCE ==================
@bot.callback_query_handler(func=lambda call: call.data == "deposit_usdt")
def deposit_usdt(call):
    bot.answer_callback_query(call.id)
    order_code = generate_order_code()
    orders.insert_one({
        "order_code": order_code,
        "user_id": call.from_user.id,
        "type": "deposit_binance",
        "amount": 0,
        "status": "pending",
        "created_at": datetime.now()
    })
    
    lang = get_user(call.from_user.id).get("language", "vi")
    text = f"""
🔄 **NẠP USDT QUA BINANCE**

📌 Chuyển tối thiểu **1 USDT** đến Binance User ID:
**{BINANCE_ADMIN_ID}**

Sau khi chuyển, hãy gửi lại **TXID** hoặc ảnh chụp màn hình cho bot để Admin duyệt.

Mã đơn: **#{order_code}**

⚠️ Chỉ chấp nhận USDT (TRC20 hoặc BEP20 khuyến nghị)
    """ if lang == "vi" else f"""
🔄 **DEPOSIT USDT VIA BINANCE**

📌 Send minimum **1 USDT** to Binance User ID:
**{BINANCE_ADMIN_ID}**

After transfer, send **TXID** or screenshot to the bot for Admin approval.

Order ID: **#{order_code}**

⚠️ Only USDT accepted (TRC20 or BEP20 recommended)
    """
    bot.send_message(call.message.chat.id, text)

def handle_deposit_amount(call):
    if call.data == "deposit_custom":
        bot.send_message(call.message.chat.id, "Nhập số tiền muốn nạp (tối thiểu 2.000đ):")
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
        if amount < 2000:
            return bot.reply_to(message, "❌ Số tiền tối thiểu là 2.000đ!")
        create_deposit_payment(message.chat.id, message.from_user.id, amount)
    except ValueError:
        bot.reply_to(message, "❌ Vui lòng nhập số tiền hợp lệ!")
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

    # SỬA Ở ĐÂY: Mô tả là mã đơn hàng
    payment_data = CreatePaymentLinkRequest(
        order_code=order_code,
        amount=amount,
        description=f"Nap #{order_code}",   # <-- Đây là phần đã sửa
        return_url="https://t.me/" + bot.get_me().username,
        cancel_url="https://t.me/" + bot.get_me().username
    )
    payment_link = payos.payment_requests.create(payment_data)

    bot.send_message(chat_id, f"""
💰 **Nạp tiền vào ví**

Mã đơn: #{order_code}
Số tiền: **{amount:,}đ**

🔗 [Thanh toán ngay]({payment_link.checkout_url})
    """, parse_mode='Markdown')

# ================== MUA HÀNG & XỬ LÝ EMAIL ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    code = call.data.split("_")[1]
    info = CATEGORIES.get(code)
    if not info: return bot.send_message(call.message.chat.id, "❌ Sản phẩm không tồn tại!")

    user = get_user(call.from_user.id)
    price = info["price"]
    stock_count = get_stock_count(code)

    if stock_count <= 0:
        return bot.send_message(call.message.chat.id, "❌ Sản phẩm đã hết hàng!")

    if code in ["canva1slot", "youtube1slot"]:
        if user.get("balance", 0) < price:
            return bot.send_message(call.message.chat.id, f"❌ Số dư ví không đủ!\nCần {price:,}đ\nHiện có: {user.get('balance', 0):,}đ\nVui lòng nạp trước.")

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

        bot.send_message(call.message.chat.id, f"""
✅ Đã trừ {price:,}đ từ ví!

📧 Vui lòng gửi **email (@gmail.com)** của bạn ngay bây giờ.
        """)
        return

    # Các sản phẩm khác (giữ nguyên)
    if user.get("balance", 0) >= price:
        update_balance(call.from_user.id, -price)
        stock_doc = stocks.find_one({"category": code})
        if stock_doc and stock_doc.get("accounts"):
            account = stock_doc["accounts"].pop(0)
            stocks.update_one({"category": code}, {"$set": {"accounts": stock_doc["accounts"]}})
            bot.send_message(call.message.chat.id, f"""
🎉 **Mua thành công từ ví!**

Sản phẩm: {info['name']}
Tài khoản: {account}
Số dư còn lại: {user.get('balance', 0) - price:,}đ
            """)
    else:
        # Tạo đơn PayOS cho sản phẩm thường
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
        bot.send_message(call.message.chat.id, f"""
✅ Đơn hàng #{order_code} đã tạo!

💰 Số tiền: {price:,}đ
📦 Sản phẩm: {info['name']}

🔗 [Thanh toán ngay]({payment_link.checkout_url})
        """, parse_mode='Markdown')

@bot.message_handler(func=lambda m: True)
def handle_user_message(message):
    # Xử lý email cho Canva & YouTube 1 Slot
    pending = orders.find_one({"user_id": message.from_user.id, "status": "waiting_email"})
    if pending:
        email = message.text.strip()
        if not re.match(r'^[\w\.-]+@gmail\.com$', email, re.IGNORECASE):
            bot.reply_to(message, "❌ Chỉ chấp nhận email @gmail.com!" if get_user(message.from_user.id).get("language")=="vi" else "❌ Only @gmail.com email accepted!")
            return
        # Gửi cho admin...
        bot.send_message(ADMIN_ID, f"📨 YÊU CẦU EMAIL - Mã đơn #{pending['order_code']}\nEmail: {email}")
        orders.update_one({"_id": pending["_id"]}, {"$set": {"status": "waiting_admin", "user_email": email}})
        bot.reply_to(message, "✅ Email đã được gửi cho admin!" if get_user(message.from_user.id).get("language")=="vi" else "✅ Email sent to admin!")

# ================== FLASK KEEP ALIVE ==================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running on Render!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)
    print("🚀 Bot Telegram Shop đã chạy!")
    bot.infinity_polling()
