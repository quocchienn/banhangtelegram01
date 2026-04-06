import telebot
import random
import os
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from payos import PayOS
from payos.types import CreatePaymentLinkRequest
from flask import Flask, request, jsonify
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
WEBHOOK_URL = os.getenv('WEBHOOK_URL')   # https://banhangtelegram01.onrender.com

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

def notify_admin(order, is_auto=False):
    user = get_user(order["user_id"])
    status = "TỰ ĐỘNG" if is_auto else ""
    if order.get("type") == "deposit":
        text = f"""
💰 **ĐƠN NẠP TIỀN {status}**
Mã đơn: #{order['order_code']}
User ID: `{order['user_id']}`
Tên: {user.get('first_name', 'Không tên')}
Số tiền: **{order.get('amount', 0):,}đ**
Trạng thái: {'ĐÃ CỘNG TIỀN' if is_auto else 'Chờ thanh toán'}
        """
    try:
        bot.send_message(ADMIN_ID, text)
    except:
        pass

# ====================== ADMIN COMMANDS ======================
@bot.message_handler(commands=['users', 'balance'])
def admin_view_balances(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    try:
        all_users = users.find().sort("balance", -1)
        text = "📊 **DANH SÁCH SỐ DƯ USER**\n\n"
        for u in all_users:
            name = u.get('first_name') or u.get('username') or 'Unknown'
            text += f"👤 {name} (ID: `{u['user_id']}`) → 💰 `{u.get('balance', 0):,}đ`\n"
        bot.send_message(message.chat.id, text, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['duyetnap'])
def admin_duyet_nap(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin!")
    try:
        order_code = int(message.text.split()[1])
        order = orders.find_one({"order_code": order_code, "type": "deposit", "status": "pending"})
        if not order:
            return bot.reply_to(message, "❌ Không tìm thấy đơn pending!")
        update_balance(order['user_id'], order['amount'])
        orders.update_one({"order_code": order_code}, {"$set": {"status": "approved"}})
        bot.send_message(order['user_id'], f"✅ Nạp tiền thủ công đã duyệt! +{order['amount']:,}đ")
        bot.reply_to(message, f"✅ Đã duyệt thủ công #{order_code}")
    except:
        bot.reply_to(message, "Sử dụng: /duyetnap <mã đơn>")

@bot.message_handler(commands=['giao'])
def admin_giao(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin!")
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
        orders.update_one({"order_code": order_code}, {"$set": {"status": "delivered", "account": account}})
        bot.reply_to(message, f"✅ Đã giao thành công đơn #{order_code}")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}\nSử dụng: /giao <mã đơn>")

@bot.message_handler(commands=['resetcanva1'])
def admin_reset_canva1(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin!")
    stocks.update_one({"category": "canva1slot"}, {"$set": {"accounts": ["Slot sẵn sàng"] * 100}}, upsert=True)
    bot.reply_to(message, "✅ Đã reset Canva 1 Slot về **100 slot**!")

@bot.message_handler(commands=['resetyoutube'])
def admin_reset_youtube(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin!")
    stocks.update_one({"category": "youtube1slot"}, {"$set": {"accounts": ["Slot sẵn sàng"] * 10}}, upsert=True)
    bot.reply_to(message, "✅ Đã reset YouTube 1 Slot về **10 slot**!")

# ====================== /start ======================
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

# ====================== CALLBACK & NẠP TIỀN ======================
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
        print("Lỗi callback:", str(e))

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

def deposit_menu(call):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("50.000đ", callback_data="deposit_50000"))
    markup.add(telebot.types.InlineKeyboardButton("100.000đ", callback_data="deposit_100000"))
    markup.add(telebot.types.InlineKeyboardButton("200.000đ", callback_data="deposit_200000"))
    markup.add(telebot.types.InlineKeyboardButton("Nhập số khác", callback_data="deposit_custom"))
    bot.send_message(call.message.chat.id, "💳 Chọn số tiền muốn nạp vào ví:", reply_markup=markup)

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
    except:
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
        description=f"Nap #{order_code}",
        return_url="https://t.me/" + bot.get_me().username,
        cancel_url="https://t.me/" + bot.get_me().username
    )
    payment_link = payos.payment_requests.create(payment_data)
    bot.send_message(chat_id, f"""
💰 **NẠP TIỀN VÀO VÍ**

Mã đơn: #{order_code}
Số tiền: **{amount:,}đ**

🔗 [Thanh toán ngay]({payment_link.checkout_url})
    """, parse_mode='Markdown')

# ====================== MUA HÀNG ======================
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

    if code in ["canva1slot", "youtube1slot"]:
        if user.get("balance", 0) < price:
            return bot.send_message(call.message.chat.id, f"❌ Số dư ví không đủ!\nCần {price:,}đ")
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

📧 Vui lòng gửi **email (@gmail.com)** ngay bây giờ.
        """)
        return

    # Sản phẩm thường
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
    pending = orders.find_one({"user_id": message.from_user.id, "status": "waiting_email"})
    if pending:
        email = message.text.strip()
        if not re.match(r'^[\w\.-]+@gmail\.com$', email, re.IGNORECASE):
            return bot.reply_to(message, "❌ Chỉ chấp nhận email @gmail.com!")
        bot.send_message(ADMIN_ID, f"""
📨 **YÊU CẦU THÊM {CATEGORIES.get(pending.get('category'), {}).get('name', '1 Slot')}**

Mã đơn: #{pending['order_code']}
User ID: `{message.from_user.id}`
Tên: {message.from_user.first_name or 'Không tên'}
Email: `{email}`
        """)
        orders.update_one({"_id": pending["_id"]}, {"$set": {"status": "waiting_admin", "user_email": email}})
        bot.reply_to(message, "✅ Email đã được gửi cho admin!")
        return

# ====================== WEBHOOK ======================
flask_app = Flask(__name__)

@flask_app.route('/payos-webhook', methods=['POST'])
def payos_webhook():
    try:
        webhook_body = request.get_data()
        webhook_data = payos.webhooks.verify(webhook_body)

        if webhook_data.success and getattr(webhook_data.data, 'code', None) == '00':
            data = webhook_data.data
            order_code = data.orderCode
            amount = data.amount

            order = orders.find_one({"order_code": order_code, "type": "deposit", "status": "pending"})
            if order:
                user_id = order['user_id']
                update_balance(user_id, amount)
                orders.update_one({"order_code": order_code}, {"$set": {"status": "approved", "paid_at": datetime.now()}})

                bot.send_message(user_id, f"""
✅ **NẠP TIỀN THÀNH CÔNG TỰ ĐỘNG!**

Mã đơn: #{order_code}
Số tiền: +{amount:,}đ
Số dư hiện tại: {get_user(user_id)['balance']:,}đ
                """)
                notify_admin(order, is_auto=True)
                print(f"[WEBHOOK] Thành công - Cộng {amount}đ cho user {user_id}")
        return jsonify({"success": True}), 200
    except Exception as e:
        print("Webhook error:", str(e))
        return jsonify({"success": False}), 400

@flask_app.route('/')
def home():
    return "Bot is alive ✅"

# ====================== CHẠY BOT ======================
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    if WEBHOOK_URL:
        try:
            confirm_url = f"{WEBHOOK_URL}/payos-webhook"
            payos.webhooks.confirm(confirm_url)
            print(f"✅ Webhook confirmed thành công: {confirm_url}")
        except Exception as e:
            print(f"❌ Lỗi confirm webhook: {str(e)}")
            print("→ Đây là lỗi phổ biến. Bot vẫn chạy bình thường.")
            print("→ Sau khi service live ổn định (1-2 phút), bạn có thể thử redeploy lại.")

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)
    print("🚀 Bot đang chạy...")
    bot.infinity_polling()
