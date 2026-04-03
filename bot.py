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

load_dotenv()

# ================== CẤU HÌNH ==================
bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))
payos = PayOS(
    client_id=os.getenv('PAYOS_CLIENT_ID'),
    api_key=os.getenv('PAYOS_API_KEY'),
    checksum_key=os.getenv('PAYOS_CHECKSUM_KEY')
)
client = MongoClient(os.getenv('MONGO_URI'))
db = client['ban_taikhoan_pro']

ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

# Collections
users = db['users']
orders = db['orders']
stocks = db['stocks']
categories = db['categories']

# ================== CATEGORIES (ĐÃ TÁCH CANVA THÀNH 2 LOẠI) ==================
CATEGORIES = {
    "hotspot": {"name": "Hotspot Shield 7D", "price": 2000, "type": "normal"},
    "gemini": {"name": "Gemini Pro 1 Acc 26-29D", "price": 40000, "type": "normal"},
    "capcut": {"name": "CapCut Pro 1 Tuần", "price": 2000, "type": "normal"},
    
    # Canva 1 Slot - Cần admin duyệt
    "canva1slot": {"name": "Canva 1 Slot", "price": 2000, "type": "canva_1slot"},
    
    # Canva 100 Slot - Gửi trực tiếp
    "canva100slot": {"name": "Canva 100 Slot", "price": 30000, "type": "normal"},
}

# Khởi tạo categories
for code, info in CATEGORIES.items():
    categories.update_one(
        {"code": code},
        {"$setOnInsert": {
            "code": code,
            "name": info["name"],
            "price": info["price"],
            "type": info.get("type", "normal"),
            "enabled": True
        }},
        upsert=True
    )

# ================== HÀM HỖ TRỢ ==================
def get_user(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "username": None,
            "first_name": None,
            "balance": 0,
            "joined_at": datetime.now()
        }
        users.insert_one(user)
    return user

def update_balance(user_id, amount):
    users.update_one({"user_id": user_id}, {"$inc": {"balance": amount}})

def generate_order_code():
    return random.randint(10000000, 99999999)

# ================== COMMANDS ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    for code, info in CATEGORIES.items():
        cat_doc = categories.find_one({"code": code})
        enabled = cat_doc.get("enabled", True) if cat_doc else True
        stock_doc = stocks.find_one({"category": code})
        stock_count = len(stock_doc.get("accounts", [])) if stock_doc else 0

        if enabled and stock_count > 0:
            markup.add(telebot.types.InlineKeyboardButton(
                f"🛒 Mua {info['name']} - {info['price']:,}đ",
                callback_data=f"buy_{code}"
            ))

    markup.add(telebot.types.InlineKeyboardButton("💰 Ví của tôi", callback_data="my_wallet"))
    markup.add(telebot.types.InlineKeyboardButton("💳 Nạp tiền vào ví", callback_data="deposit"))

    bot.send_message(message.chat.id, 
        f"👋 Chào **{message.from_user.first_name}**!\n\nChọn sản phẩm bạn muốn mua:", 
        parse_mode='Markdown', reply_markup=markup)

# ================== XEM VÍ ==================
@bot.callback_query_handler(func=lambda call: call.data == "my_wallet")
def show_wallet(call):
    user = get_user(call.from_user.id)
    joined = user.get('joined_at', datetime.now()).strftime('%d/%m/%Y')

    text = f"""
🆔 **ID:** `{call.from_user.id}`
👤 **Tên:** {call.from_user.first_name or call.from_user.username or 'Không có tên'}
💰 **Số dư:** `{user.get('balance', 0):,}đ`
📅 **Tham gia:** {joined}
    """
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

# ================== NẠP TIỀN (giữ nguyên) ==================
# ... (phần nạp tiền giữ nguyên như code trước, mình rút gọn để code ngắn)

# ================== MUA HÀNG - XỬ LÝ RIÊNG CHO CANVA 1 SLOT ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    code = call.data.split("_")[1]
    info = CATEGORIES.get(code)
    if not info:
        return bot.answer_callback_query(call.id, "Sản phẩm không tồn tại!")

    user = get_user(call.from_user.id)
    price = info["price"]

    # Trường hợp Canva 1 Slot - Yêu cầu gửi mail
    if code == "canva1slot":
        order_code = generate_order_code()
        orders.insert_one({
            "order_code": order_code,
            "user_id": call.from_user.id,
            "category": code,
            "amount": price,
            "type": "purchase",
            "status": "pending",
            "created_at": datetime.now()
        })

        payment_data = CreatePaymentLinkRequest(
            order_code=order_code,
            amount=price,
            description=f"Canva 1 Slot",
            return_url="https://t.me/" + bot.get_me().username,
            cancel_url="https://t.me/" + bot.get_me().username
        )
        payment_link = payos.payment_requests.create(payment_data)

        bot.send_message(call.from_user.id, f"""
✅ Đơn hàng #{order_code} đã tạo!

💰 Số tiền: {price:,}đ
📦 Sản phẩm: Canva 1 Slot

🔗 Thanh toán tại: {payment_link.checkout_url}

Sau khi thanh toán thành công, hãy gửi **email Canva** của bạn cho bot để admin thêm vào slot.
        """)
        bot.answer_callback_query(call.id)
        return

    # Các sản phẩm khác (bao gồm Canva 100 Slot)
    if user.get("balance", 0) >= price:
        update_balance(call.from_user.id, -price)
        stock_doc = stocks.find_one({"category": code})
        if stock_doc and stock_doc.get("accounts"):
            account = stock_doc["accounts"].pop(0)
            stocks.update_one({"category": code}, {"$set": {"accounts": stock_doc["accounts"]}})

            bot.send_message(call.from_user.id, f"""
🎉 **Mua thành công từ ví!**

Sản phẩm: {info['name']}
Tài khoản: {account}
Số dư còn lại: {user['balance'] - price:,}đ
            """)
        else:
            bot.send_message(call.from_user.id, "❌ Sản phẩm tạm hết hàng!")
    else:
        # Tạo link PayOS
        order_code = generate_order_code()
        orders.insert_one({
            "order_code": order_code,
            "user_id": call.from_user.id,
            "category": code,
            "amount": price,
            "type": "purchase",
            "status": "pending",
            "created_at": datetime.now()
        })

        payment_data = CreatePaymentLinkRequest(
            order_code=order_code,
            amount=price,
            description=f"Don {order_code}",
            return_url="https://t.me/" + bot.get_me().username,
            cancel_url="https://t.me/" + bot.get_me().username
        )
        payment_link = payos.payment_requests.create(payment_data)

        bot.send_message(call.from_user.id, f"""
✅ Đơn hàng #{order_code} đã tạo!

💰 Số tiền: {price:,}đ
📦 Sản phẩm: {info['name']}

🔗 Thanh toán ngay: {payment_link.checkout_url}
        """)

    bot.answer_callback_query(call.id)

# ================== ADMIN - GIAO TÀI KHOẢN THỦ CÔNG (đã có) ==================
# (giữ nguyên lệnh /giao từ code trước)

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

    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=50)
        except Exception as e:
            print("Polling lỗi:", str(e))
            time.sleep(5)
