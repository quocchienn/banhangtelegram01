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

bot = telebot.TelegrafBot(os.getenv('BOT_TOKEN'))  # Sửa lỗi nhỏ nếu có
payos = PayOS(
    client_id=os.getenv('PAYOS_CLIENT_ID'),
    api_key=os.getenv('PAYOS_API_KEY'),
    checksum_key=os.getenv('PAYOS_CHECKSUM_KEY')
)
client = MongoClient(os.getenv('MONGO_URI'))
db = client['ban_taikhoan_pro']

ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
BINANCE_ID = "1163285604"

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

# ================== TEXT ĐA NGÔN NGỮ ==================
TEXTS = {
    "select_lang": {"vi": "🌐 Chọn ngôn ngữ / Select language:", "en": "🌐 Chọn ngôn ngữ / Select language:"},
    "welcome": {"vi": "👋 Chào **{name}**!\n\nChọn sản phẩm bạn muốn mua:", "en": "👋 Hello **{name}**!\n\nChoose the product you want to buy:"},
    "my_wallet": {"vi": "💰 Ví của tôi", "en": "💰 My Wallet"},
    "deposit": {"vi": "💳 Nạp tiền vào ví", "en": "💳 Deposit to Wallet"},
    "binance_deposit": {"vi": "💸 Binance USDT (tối thiểu 1 USDT)", "en": "💸 Binance USDT (min 1 USDT)"},
    "deposit_menu": {"vi": "💳 Chọn cách nạp tiền:", "en": "💳 Choose deposit method:"},
    "binance_instruction": {"vi": f"💸 **NẠP USDT QUA BINANCE**\n\nChuyển tối thiểu **1 USDT** đến Binance ID:\n**{BINANCE_ID}**\n\nSau khi chuyển xong, gửi mã giao dịch (TXID) hoặc screenshot cho bot.", 
                            "en": f"💸 **DEPOSIT USDT VIA BINANCE**\n\nTransfer minimum **1 USDT** to Binance ID:\n**{BINANCE_ID}**\n\nAfter transfer, send TXID or screenshot to the bot."},
    "wallet_info": {"vi": "🆔 **ID:** `{id}`\n👤 **Tên:** {name}\n💰 **Số dư:** {balance:,}đ\n📅 **Tham gia:** {date}", 
                    "en": "🆔 **ID:** `{id}`\n👤 **Name:** {name}\n💰 **Balance:** {balance:,}đ\n📅 **Joined:** {date}"},
    "email_request": {"vi": "✅ Đã trừ tiền!\n\n📧 Vui lòng gửi **email (@gmail.com)** của bạn ngay bây giờ.", 
                      "en": "✅ Deducted!\n\n📧 Please send your **email (@gmail.com)** now."},
    "proof_sent": {"vi": "✅ Proof đã được gửi cho admin. Vui lòng chờ duyệt!", 
                   "en": "✅ Proof sent to admin. Please wait for approval!"}
}

def t(key, lang="vi", **kwargs):
    text = TEXTS.get(key, {}).get(lang, TEXTS.get(key, {}).get("vi", key))
    return text.format(**kwargs) if kwargs else text

# Khởi tạo categories
for code, info in CATEGORIES.items():
    categories.update_one({"code": code}, {"$setOnInsert": {
        "code": code, "name": info["name"], "price": info["price"], "type": info.get("type"), "enabled": True
    }}, upsert=True)

def get_user(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id, 
            "first_name": None, 
            "balance": 0, 
            "language": "vi", 
            "joined_at": datetime.now()
        }
        users.insert_one(user)
    if "language" not in user:
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

def notify_admin(order):
    user = get_user(order["user_id"])
    cat_name = CATEGORIES.get(order.get("category"), {}).get("name", "Nạp tiền")
    if order.get("type") in ["deposit", "binance"]:
        text = f"""
💰 **ĐƠN NẠP TIỀN MỚI**
Mã đơn: #{order['order_code']}
User ID: `{order['user_id']}`
Tên: {user.get('first_name', 'Không tên')}
Số tiền: **{order.get('amount', 0):,}đ**
Loại: {order.get('type')}
        """
    else:
        text = f"""
🛒 **ĐƠN MUA HÀNG**
Mã đơn: #{order['order_code']}
User ID: `{order['user_id']}`
Sản phẩm: {cat_name}
Số tiền: **{order.get('amount', 0):,}đ**
        """
    try:
        bot.send_message(ADMIN_ID, text)
    except:
        pass

# ================== /START ==================
@bot.message_handler(commands=['start'])
def start(message):
    user = get_user(message.from_user.id)
    lang = user.get("language", "vi")

    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    for code, info in CATEGORIES.items():
        stock_count = get_stock_count(code)
        btn_text = f"🛒 Mua {info['name']} - {info['price']:,}đ (còn {stock_count})" if stock_count > 0 else f"{info['name']} - 🔒 Hết hàng"
        markup.add(telebot.types.InlineKeyboardButton(btn_text, callback_data=f"buy_{code}" if stock_count > 0 else "outofstock"))

    markup.add(telebot.types.InlineKeyboardButton(t("my_wallet", lang), callback_data="my_wallet"))
    markup.add(telebot.types.InlineKeyboardButton(t("deposit", lang), callback_data="deposit"))

    bot.send_message(message.chat.id, t("welcome", lang, name=message.from_user.first_name), 
                     parse_mode='Markdown', reply_markup=markup)

# ================== CALLBACK HANDLER ==================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    user = get_user(call.from_user.id)
    lang = user.get("language", "vi")

    try:
        if call.data == "my_wallet":
            show_wallet(call, lang)
        elif call.data == "deposit":
            deposit_menu(call, lang)
        elif call.data.startswith("deposit_"):
            handle_deposit(call, lang)
        elif call.data.startswith("buy_"):
            handle_buy(call, lang)
        elif call.data == "outofstock":
            bot.send_message(call.message.chat.id, "❌ Sản phẩm đã hết hàng!" if lang == "vi" else "❌ Product is out of stock!")
    except Exception as e:
        print("Callback error:", e)

def show_wallet(call, lang):
    user = get_user(call.from_user.id)
    joined = user.get('joined_at', datetime.now()).strftime('%d/%m/%Y')
    text = t("wallet_info", lang, id=call.from_user.id, name=call.from_user.first_name or 'Không tên', 
             balance=user.get('balance', 0), date=joined)
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

def deposit_menu(call, lang):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("50.000đ", callback_data="deposit_50000"))
    markup.add(telebot.types.InlineKeyboardButton("100.000đ", callback_data="deposit_100000"))
    markup.add(telebot.types.InlineKeyboardButton("200.000đ", callback_data="deposit_200000"))
    markup.add(telebot.types.InlineKeyboardButton(t("binance_deposit", lang), callback_data="deposit_binance"))
    markup.add(telebot.types.InlineKeyboardButton("Nhập số khác" if lang == "vi" else "Other amount", callback_data="deposit_custom"))
    bot.send_message(call.message.chat.id, t("deposit_menu", lang), reply_markup=markup)

def handle_deposit(call, lang):
    data = call.data
    if data == "deposit_binance":
        handle_binance_deposit(call, lang)
        return
    if data == "deposit_custom":
        bot.send_message(call.message.chat.id, "Nhập số tiền muốn nạp (tối thiểu 2.000đ):" if lang == "vi" else "Enter amount (min 2000đ):")
        bot.register_next_step_handler(call.message, process_custom_deposit)
        return
    try:
        amount = int(data.split("_")[1])
        create_payos_deposit(call.message.chat.id, call.from_user.id, amount, lang)
    except:
        bot.send_message(call.message.chat.id, "❌ Có lỗi xảy ra!")

def process_custom_deposit(message):
    user = get_user(message.from_user.id)
    lang = user.get("language", "vi")
    try:
        amount = int(message.text.strip())
        if amount < 2000:
            return bot.reply_to(message, "❌ Số tiền tối thiểu là 2.000đ!" if lang == "vi" else "❌ Minimum 2,000đ!")
        create_payos_deposit(message.chat.id, message.from_user.id, amount, lang)
    except:
        bot.reply_to(message, "❌ Vui lòng nhập số hợp lệ!")

def create_payos_deposit(chat_id, user_id, amount, lang):
    order_code = generate_order_code()
    order = {"order_code": order_code, "user_id": user_id, "type": "deposit", "amount": amount, "status": "pending", "created_at": datetime.now()}
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

    bot.send_message(chat_id, f"""
💰 **Nạp tiền PayOS**
Mã đơn: #{order_code}
Số tiền: **{amount:,}đ**

🔗 [Thanh toán ngay]({payment_link.checkout_url})
    """, parse_mode='Markdown')

def handle_binance_deposit(call, lang):
    order_code = generate_order_code()
    order = {
        "order_code": order_code,
        "user_id": call.from_user.id,
        "type": "binance",
        "amount": 0,
        "status": "pending_proof",
        "created_at": datetime.now()
    }
    orders.insert_one(order)
    notify_admin(order)

    bot.send_message(call.message.chat.id, t("binance_instruction", lang))

# ================== MUA HÀNG ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call, lang=None):
    if not lang:
        user = get_user(call.from_user.id)
        lang = user.get("language", "vi")
    code = call.data.split("_")[1]
    info = CATEGORIES.get(code)
    if not info:
        return bot.send_message(call.message.chat.id, "❌ Sản phẩm không tồn tại!")

    user = get_user(call.from_user.id)
    price = info["price"]
    stock_count = get_stock_count(code)

    if stock_count <= 0:
        return bot.send_message(call.message.chat.id, "❌ Sản phẩm đã hết hàng!")

    if code in ["canva1slot", "youtube1slot"]:
        if user.get("balance", 0) < price:
            return bot.send_message(call.message.chat.id, t("insufficient_balance", lang, price=price) if "insufficient_balance" in TEXTS else "❌ Số dư không đủ!")

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

        bot.send_message(call.message.chat.id, t("email_request", lang))
        return

    # Các sản phẩm khác
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
Số dư còn lại: {user.get('balance', 0) - price:,}đ
            """)
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
        bot.send_message(call.message.chat.id, f"""
✅ Đơn hàng #{order_code} đã tạo!

Số tiền: {price:,}đ
Sản phẩm: {info['name']}

🔗 [Thanh toán ngay]({payment_link.checkout_url})
        """, parse_mode='Markdown')

# ================== XỬ LÝ TIN NHẮN (Email + Binance Proof) ==================
@bot.message_handler(func=lambda m: True)
def handle_user_message(message):
    user = get_user(message.from_user.id)
    lang = user.get("language", "vi")

    # Email cho Canva / YouTube
    pending = orders.find_one({"user_id": message.from_user.id, "status": "waiting_email"})
    if pending:
        email = message.text.strip()
        if not re.match(r'^[\w\.-]+@gmail\.com$', email, re.IGNORECASE):
            return bot.reply_to(message, "❌ Chỉ chấp nhận email @gmail.com!")
        bot.send_message(ADMIN_ID, f"""
📨 **YÊU CẦU THÊM SLOT**
Mã đơn: #{pending['order_code']}
User: `{message.from_user.id}`
Email: `{email}`
        """)
        orders.update_one({"_id": pending["_id"]}, {"$set": {"status": "waiting_admin", "user_email": email}})
        bot.reply_to(message, "✅ Email đã gửi cho admin!")
        return

    # Proof Binance
    pending_binance = orders.find_one({"user_id": message.from_user.id, "type": "binance", "status": "pending_proof"})
    if pending_binance:
        bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        bot.send_message(ADMIN_ID, f"""
💸 **PROOF NẠP BINANCE**
Mã đơn: #{pending_binance['order_code']}
User ID: `{message.from_user.id}`
        """)
        bot.reply_to(message, t("proof_sent", lang))
        orders.update_one({"_id": pending_binance["_id"]}, {"$set": {"status": "waiting_approval"}})
        return

# ================== FLASK KEEP-ALIVE ==================
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
    print("🚀 Bot Telegram Shop đã chạy!")
    bot.infinity_polling()
