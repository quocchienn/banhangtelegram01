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

CATEGORIES = {
    "hotspot": {"name": "Hotspot Shield 7D", "price": 2000, "type": "normal"},
    "gemini": {"name": "Gemini Pro 1 Acc 26-29D", "price": 40000, "type": "normal"},
    "capcut": {"name": "CapCut Pro 1 Tuần", "price": 2000, "type": "normal"},
    "meitu": {"name": "Meitu 1 Tuần", "price": 2000, "type": "normal"},
    "wink": {"name": "Wink 1 Tuần", "price": 2000, "type": "normal"},
    "canva1slot": {"name": "Canva 1 Slot", "price": 2000, "type": "canva_1slot"},
    "canva100slot": {"name": "Canva 100 Slot", "price": 30000, "type": "normal"},
    "youtube1slot": {"name": "YouTube 1 Slot", "price": 2000, "type": "youtube_1slot"},   # <-- Mới thêm
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
Trạng thái: Chờ thanh toán
        """
    else:
        text = f"""
🛒 **ĐƠN MUA HÀNG MỚI**
Mã đơn: #{order['order_code']}
User ID: `{order['user_id']}`
Tên: {user.get('first_name', 'Không tên')}
Sản phẩm: {cat_name}
Số tiền: **{order['amount']:,}đ**
Trạng thái: Chờ thanh toán
        """
    try:
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
    stocks.update_one(
        {"category": "canva1slot"},
        {"$set": {"accounts": ["Slot sẵn sàng"] * 100}},
        upsert=True
    )
    bot.reply_to(message, "✅ Đã reset Canva 1 Slot về **100 slot** và mở bán lại!")

# ================== RESET YOUTUBE 1 SLOT (Mới thêm) ==================
@bot.message_handler(commands=['resetyoutube'])
def admin_reset_youtube(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    stocks.update_one(
        {"category": "youtube1slot"},
        {"$set": {"accounts": ["Slot sẵn sàng"] * 10}},
        upsert=True
    )
    bot.reply_to(message, "✅ Đã reset YouTube 1 Slot về **10 slot** và mở bán lại!")

# ================== UPLOAD FILE TXT ==================
@bot.message_handler(content_types=['document'])
def handle_document(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới được upload file!")

    try:
        file_name = (message.document.file_name or "").lower()
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        content = downloaded_file.decode('utf-8')

        lines = [line.strip() for line in content.split('\n') if line.strip()]

        category = None
        for code, info in CATEGORIES.items():
            if any(kw in file_name for kw in [code.lower(), info["name"].lower()]):
                category = code
                break

        if category:
            added = 0
            for line in lines:
                if line:
                    stocks.update_one({"category": category}, {"$push": {"accounts": line}}, upsert=True)
                    added += 1
            bot.reply_to(message, f"✅ Đã tự động thêm **{added}** tài khoản vào **{CATEGORIES[category]['name']}**")
        else:
            markup = telebot.types.InlineKeyboardMarkup(row_width=2)
            for code, info in CATEGORIES.items():
                markup.add(telebot.types.InlineKeyboardButton(info["name"], callback_data=f"update_stock_{code}"))
            bot.reply_to(message, "File đã nhận. Chọn loại tài khoản để cập nhật:", reply_markup=markup)
            if not hasattr(bot, 'pending_files'):
                bot.pending_files = {}
            bot.pending_files[message.from_user.id] = {"content": lines}

    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi xử lý file: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("update_stock_"))
def update_stock_callback(call):
    bot.answer_callback_query(call.id)
    category = call.data.split("_")[2]
    if not hasattr(bot, 'pending_files') or call.from_user.id not in bot.pending_files:
        return bot.send_message(call.message.chat.id, "❌ Không tìm thấy file!")
    lines = bot.pending_files[call.from_user.id]["content"]
    added = 0
    for line in lines:
        if line:
            stocks.update_one({"category": category}, {"$push": {"accounts": line}}, upsert=True)
            added += 1
    del bot.pending_files[call.from_user.id]
    bot.edit_message_text(f"✅ Đã thêm **{added}** tài khoản vào **{CATEGORIES[category]['name']}**", 
                          call.message.chat.id, call.message.message_id)

# ================== MUA HÀNG ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    code = call.data.split("_")[1]
    info = CATEGORIES.get(code)
    if not info:
        return bot.send_message(call.message.chat.id, "❌ Sản phẩm không tồn tại!")

    user = get_user(call.from_user.id)
    price = info["price"]
    stock_count = get_stock_count(code)

    if stock_count <= 0:
        return bot.send_message(call.message.chat.id, "❌ Sản phẩm đã hết hàng!")

    if code in ["canva1slot", "youtube1slot"]:   # Cả 2 loại đặc biệt
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

📧 Vui lòng gửi **email** của bạn ngay bây giờ.
        """)
        return

    # Các sản phẩm khác
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
Số dư còn lại: {user['balance'] - price:,}đ
            """)
        else:
            bot.send_message(call.message.chat.id, "❌ Sản phẩm tạm hết hàng!")
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
            description=f"Don {order_code}",
            return_url="https://t.me/" + bot.get_me().username,
            cancel_url="https://t.me/" + bot.get_me().username
        )
        payment_link = payos.payment_requests.create(payment_data)

        bot.send_message(call.message.chat.id, f"""
✅ Đơn hàng #{order_code} đã tạo!

💰 Số tiền: {price:,}đ
📦 Sản phẩm: {info['name']}

🔗 [Thanh toán ngay]({payment_link.checkout_url})
        """)

# ================== XỬ LÝ EMAIL CHO CẢ CANVA 1 SLOT VÀ YOUTUBE 1 SLOT ==================
@bot.message_handler(func=lambda m: True)
def handle_user_message(message):
    pending = orders.find_one({
        "user_id": message.from_user.id,
        "status": "waiting_email"
    })
    if pending and pending.get("type") in ["canva_1slot", "youtube1slot"]:
        email = message.text.strip()
        if not re.match(r'^[\w\.-]+@gmail\.com$', email, re.IGNORECASE):
            return bot.reply_to(message, "❌ Chỉ chấp nhận email @gmail.com!\nVui lòng gửi lại đúng định dạng.")

        bot.send_message(ADMIN_ID, f"""
📨 **YÊU CẦU THÊM {CATEGORIES.get(pending['category'], {}).get('name', '1 Slot')}**

Mã đơn: #{pending['order_code']}
User ID: `{message.from_user.id}`
Tên: {message.from_user.first_name or 'Không tên'}
Email: `{email}`
        """)

        orders.update_one({"_id": pending["_id"]}, {"$set": {"status": "waiting_admin", "user_email": email}})
        bot.reply_to(message, "✅ Email đã được gửi cho admin!")
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
