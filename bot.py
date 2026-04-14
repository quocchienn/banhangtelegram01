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
BINANCE_ID = "1163285604"
USDT_TO_VND = 25000  # 1 USDT = 25.000 VND

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

# ================== NGÔN NGỮ ==================
LANGUAGES = {
    "vi": {
        "welcome": "👋 Chào **{name}**!\n\nChọn sản phẩm bạn muốn mua:",
        "my_wallet": "💰 Ví của tôi",
        "deposit": "💳 Nạp tiền vào ví",
        "deposit_usdt": "💸 Nạp USDT Binance",
        "choose_lang": "🌐 Chọn ngôn ngữ / Choose language",
        "lang_vi": "🇻🇳 Tiếng Việt",
        "lang_en": "🇬🇧 English",
    },
    "en": {
        "welcome": "👋 Hello **{name}**!\n\nChoose the product you want to buy:",
        "my_wallet": "💰 My Wallet",
        "deposit": "💳 Deposit to Wallet",
        "deposit_usdt": "💸 Deposit USDT via Binance",
        "choose_lang": "🌐 Choose language",
        "lang_vi": "🇻🇳 Vietnamese",
        "lang_en": "🇬🇧 English",
    }
}

def get_text(key, lang="vi"):
    return LANGUAGES.get(lang, LANGUAGES["vi"]).get(key, key)

def get_user(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "username": None,
            "first_name": None,
            "balance": 0,
            "language": "vi",          # Ngôn ngữ mặc định
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

def notify_admin(order, lang="vi"):
    user = get_user(order["user_id"])
    cat_name = CATEGORIES.get(order.get("category"), {}).get("name", "Nạp tiền")
    if order["type"] == "deposit":
        text = f"💰 **NEW DEPOSIT**\nMã đơn: #{order['order_code']}\nUser: `{order['user_id']}`\nSố tiền: **{order['amount']:,}đ**"
    elif order["type"] == "deposit_usdt":
        text = f"💸 **NEW USDT DEPOSIT**\nMã đơn: #{order['order_code']}\nUser: `{order['user_id']}`\nSố USDT: **{order.get('amount_usdt', 0)}**"
    else:
        text = f"🛒 **NEW ORDER**\nMã đơn: #{order['order_code']}\nSản phẩm: {cat_name}"
    try:
        bot.send_message(ADMIN_ID, text)
    except:
        pass

# ================== /start - Chọn ngôn ngữ ==================
@bot.message_handler(commands=['start'])
def start(message):
    user = get_user(message.from_user.id)
    lang = user.get("language", "vi")

    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="set_lang_vi"),
        telebot.types.InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")
    )
    markup.add(telebot.types.InlineKeyboardButton(get_text("my_wallet", lang), callback_data="my_wallet"))
    markup.add(telebot.types.InlineKeyboardButton(get_text("deposit", lang), callback_data="deposit"))

    bot.send_message(
        message.chat.id,
        get_text("choose_lang", lang) if user.get("language") is None else get_text("welcome", lang).format(name=message.from_user.first_name),
        parse_mode='Markdown',
        reply_markup=markup
    )

# ================== Chọn ngôn ngữ ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("set_lang_"))
def set_language(call):
    bot.answer_callback_query(call.id)
    lang_code = "vi" if call.data == "set_lang_vi" else "en"
    users.update_one({"user_id": call.from_user.id}, {"$set": {"language": lang_code}})
    start(call.message)  # Reload menu theo ngôn ngữ mới

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
        bot.send_message(user_id, f"✅ Nạp tiền đã được duyệt!\nSố tiền: +{amount:,}đ\nSố dư hiện tại: {get_user(user_id)['balance']:,}đ")
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
        bot.send_message(user_id, f"""
🎉 **Tài khoản đã được giao!**

Đơn: #{order_code}
Sản phẩm: {CATEGORIES.get(category, {}).get('name', category)}
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
    joined = user.get('joined_at', datetime.now()).strftime('%d/%m/%Y')
    text = f"""
🆔 **ID:** `{call.from_user.id}`
👤 **Tên:** {call.from_user.first_name or 'Không có tên'}
💰 **Số dư:** `{user.get('balance', 0):,}đ`
📅 **Tham gia:** {joined}
    """
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

# ================== NẠP TIỀN (VNĐ + USDT) ==================
@bot.callback_query_handler(func=lambda call: call.data == "deposit")
def deposit_menu(call):
    user = get_user(call.from_user.id)
    lang = user.get("language", "vi")
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("50.000đ", callback_data="deposit_50000"))
    markup.add(telebot.types.InlineKeyboardButton("100.000đ", callback_data="deposit_100000"))
    markup.add(telebot.types.InlineKeyboardButton("200.000đ", callback_data="deposit_200000"))
    markup.add(telebot.types.InlineKeyboardButton("Nhập số khác", callback_data="deposit_custom"))
    markup.add(telebot.types.InlineKeyboardButton(get_text("deposit_usdt", lang), callback_data="deposit_usdt_binance"))
    bot.send_message(call.message.chat.id, "💳 Chọn hình thức nạp tiền:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "deposit_usdt_binance")
def deposit_usdt_binance(call):
    user = get_user(call.from_user.id)
    lang = user.get("language", "vi")
    text = f"""
💸 **NẠP USDT QUA BINANCE**

📍 Binance ID: `{BINANCE_ID}`
💰 Tối thiểu: 1 USDT
💱 Tỷ giá: 1 USDT = {USDT_TO_VND:,} VND

✅ Sau khi chuyển, hãy gửi:
1. Ảnh proof (screenshot giao dịch)
2. Số USDT bạn đã chuyển

Bot sẽ tạo đơn và chờ admin duyệt.
    """
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
    # Lưu trạng thái chờ proof
    orders.insert_one({
        "order_code": generate_order_code(),
        "user_id": call.from_user.id,
        "type": "deposit_usdt",
        "status": "waiting_proof",
        "created_at": datetime.now()
    })

# Xử lý ảnh proof USDT
@bot.message_handler(content_types=['photo', 'document'])
def handle_usdt_proof(message):
    pending = orders.find_one({"user_id": message.from_user.id, "type": "deposit_usdt", "status": "waiting_proof"})
    if pending:
        order_code = pending["order_code"]
        bot.send_message(ADMIN_ID, f"""
💸 **PROOF USDT MỚI**
Mã đơn: #{order_code}
User ID: `{message.from_user.id}`
Tên: {message.from_user.first_name}
        """)
        bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        bot.reply_to(message, "✅ Ảnh proof đã được gửi cho admin.\nVui lòng chờ duyệt!")
        orders.update_one({"order_code": order_code}, {"$set": {"status": "pending_approval"}})

# Lệnh admin duyệt USDT
@bot.message_handler(commands=['duyetusdt'])
def admin_duyet_usdt(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        order_code = int(message.text.split()[1])
        order = orders.find_one({"order_code": order_code, "type": "deposit_usdt", "status": "pending_approval"})
        if not order:
            return bot.reply_to(message, "❌ Không tìm thấy đơn USDT!")
        
        # Giả sử user đã khai báo số USDT (bạn có thể yêu cầu user nhập số USDT trước khi gửi ảnh)
        amount_usdt = 1.0  # Tạm mặc định, sau có thể cải tiến
        amount_vnd = int(amount_usdt * USDT_TO_VND)
        
        update_balance(order["user_id"], amount_vnd)
        orders.update_one({"order_code": order_code}, {"$set": {"status": "approved", "amount": amount_vnd, "amount_usdt": amount_usdt}})
        
        bot.send_message(order["user_id"], f"✅ Nạp USDT đã được duyệt!\n+{amount_vnd:,}đ vào ví\nSố dư hiện tại: {get_user(order['user_id'])['balance']:,}đ")
        bot.reply_to(message, f"✅ Đã duyệt USDT #{order_code} - Cộng {amount_vnd:,}đ")
    except:
        bot.reply_to(message, "Sử dụng: /duyetusdt <mã đơn>")

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
