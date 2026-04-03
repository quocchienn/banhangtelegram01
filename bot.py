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

# Categories
CATEGORIES = {
    "hotspot": {"name": "Hotspot Shield 7D", "price": 2000, "type": "normal"},
    "gemini": {"name": "Gemini Pro 1 Acc 26-29D", "price": 40000, "type": "normal"},
    "capcut": {"name": "CapCut Pro 1 Tuần", "price": 2000, "type": "normal"},
    "canva1slot": {"name": "Canva 1 Slot", "price": 2000, "type": "canva_1slot", "max_slots": 100},
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
            "max_slots": info.get("max_slots", 0),
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

def get_stock_count(category):
    stock_doc = stocks.find_one({"category": category})
    return len(stock_doc.get("accounts", [])) if stock_doc else 0

# ================== START MENU ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    has_available = False

    for code, info in CATEGORIES.items():
        cat_doc = categories.find_one({"code": code})
        enabled = cat_doc.get("enabled", True) if cat_doc else True
        stock_count = get_stock_count(code)

        if enabled and stock_count > 0:
            has_available = True
            markup.add(telebot.types.InlineKeyboardButton(
                f"🛒 Mua {info['name']} - {info['price']:,}đ (còn {stock_count})",
                callback_data=f"buy_{code}"
            ))
        else:
            status = "🔒 Hết hàng" if stock_count == 0 else "🔧 Tạm khóa"
            markup.add(telebot.types.InlineKeyboardButton(
                f"{info['name']} - {status}",
                callback_data=f"info_outofstock_{code}"
            ))

    markup.add(telebot.types.InlineKeyboardButton("💰 Ví của tôi", callback_data="my_wallet"))
    markup.add(telebot.types.InlineKeyboardButton("💳 Nạp tiền vào ví", callback_data="deposit"))

    bot.send_message(message.chat.id, 
        f"👋 Chào **{message.from_user.first_name}**!\n\nChọn sản phẩm bạn muốn mua:", 
        parse_mode='Markdown', reply_markup=markup)

# ================== CALLBACK HANDLER ==================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        data = call.data

        if data == "my_wallet":
            show_wallet(call)
        elif data == "deposit":
            deposit_menu(call)
        elif data.startswith("deposit_"):
            handle_deposit(call)
        elif data.startswith("buy_"):
            handle_buy(call)
        elif data.startswith("info_outofstock_"):
            bot.answer_callback_query(call.id, "Sản phẩm hiện đang hết hàng hoặc tạm khóa!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "Chức năng đang phát triển!", show_alert=True)

    except Exception as e:
        print("Callback error:", str(e))
        bot.answer_callback_query(call.id, "❌ Có lỗi xảy ra!", show_alert=True)

# ================== XEM VÍ ==================
def show_wallet(call):
    user = get_user(call.from_user.id)
    joined = user.get('joined_at', datetime.now()).strftime('%d/%m/%Y %H:%M')

    text = f"""
🆔 **ID:** `{call.from_user.id}`
👤 **Tên:** {call.from_user.first_name or call.from_user.username or 'Không có tên'}
💰 **Số dư:** `{user.get('balance', 0):,}đ`
📅 **Tham gia:** {joined}
    """
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

# ================== NẠP TIỀN (giữ nguyên) ==================
def deposit_menu(call):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("50.000đ", callback_data="deposit_50000"))
    markup.add(telebot.types.InlineKeyboardButton("100.000đ", callback_data="deposit_100000"))
    markup.add(telebot.types.InlineKeyboardButton("200.000đ", callback_data="deposit_200000"))
    markup.add(telebot.types.InlineKeyboardButton("Nhập số khác", callback_data="deposit_custom"))

    bot.send_message(call.message.chat.id, "💳 Chọn số tiền muốn nạp vào ví:", reply_markup=markup)

def handle_deposit(call):
    if call.data == "deposit_custom":
        bot.send_message(call.message.chat.id, "Nhập số tiền muốn nạp (ví dụ: 50000):")
        bot.register_next_step_handler(call.message, process_custom_deposit)
        return

    amount = int(call.data.split("_")[1])
    order_code = generate_order_code()

    orders.insert_one({
        "order_code": order_code,
        "user_id": call.from_user.id,
        "type": "deposit",
        "amount": amount,
        "status": "pending",
        "created_at": datetime.now()
    })

    payment_data = CreatePaymentLinkRequest(
        order_code=order_code,
        amount=amount,
        description=f"Nap vi {amount}đ",
        return_url="https://t.me/" + bot.get_me().username,
        cancel_url="https://t.me/" + bot.get_me().username
    )

    payment_link = payos.payment_requests.create(payment_data)
    bot.send_message(call.message.chat.id, 
        f"💰 **Nạp tiền vào ví**\n\n"
        f"Số tiền: {amount:,}đ\n"
        f"Mã đơn: #{order_code}\n\n"
        f"🔗 Thanh toán tại: {payment_link.checkout_url}", 
        parse_mode='Markdown')

def process_custom_deposit(message):
    try:
        amount = int(message.text.strip())
        if amount < 10000:
            return bot.reply_to(message, "Số tiền tối thiểu là 10.000đ!")

        order_code = generate_order_code()
        orders.insert_one({
            "order_code": order_code,
            "user_id": message.from_user.id,
            "type": "deposit",
            "amount": amount,
            "status": "pending",
            "created_at": datetime.now()
        })

        payment_data = CreatePaymentLinkRequest(
            order_code=order_code,
            amount=amount,
            description=f"Nap vi {amount}đ",
            return_url="https://t.me/" + bot.get_me().username,
            cancel_url="https://t.me/" + bot.get_me().username
        )
        payment_link = payos.payment_requests.create(payment_data)

        bot.send_message(message.chat.id, 
            f"💰 **Nạp tiền vào ví**\n\n"
            f"Số tiền: {amount:,}đ\n"
            f"Mã đơn: #{order_code}\n\n"
            f"🔗 Thanh toán tại: {payment_link.checkout_url}", 
            parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "Vui lòng nhập số tiền hợp lệ!")
    except Exception as e:
        bot.reply_to(message, f"Lỗi: {str(e)}")

# ================== MUA HÀNG - XỬ LÝ CANVA 1 SLOT ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    code = call.data.split("_")[1]
    info = CATEGORIES.get(code)
    if not info:
        return bot.answer_callback_query(call.id, "Sản phẩm không tồn tại!")

    stock_count = get_stock_count(code)

    if stock_count == 0 and code != "canva1slot":
        return bot.answer_callback_query(call.id, "❌ Sản phẩm đã hết hàng!", show_alert=True)

    user = get_user(call.from_user.id)
    price = info["price"]

    # === CANVA 1 SLOT - Yêu cầu gửi email ===
    if code == "canva1slot":
        if stock_count >= 100:  # Giới hạn tối đa 100 slot
            order_code = generate_order_code()
            orders.insert_one({
                "order_code": order_code,
                "user_id": call.from_user.id,
                "category": code,
                "amount": price,
                "type": "canva_1slot",
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

Sau khi thanh toán thành công, **hãy gửi email Canva** của bạn cho bot.
Bot sẽ chuyển cho admin để thêm vào slot.
            """)
        else:
            bot.answer_callback_query(call.id, f"❌ Chỉ còn {stock_count} slot Canva 1 Slot!", show_alert=True)
        bot.answer_callback_query(call.id)
        return

    # === Các sản phẩm khác (trừ tiền ví nếu đủ) ===
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

# ================== ADMIN - RESET STOCK CANVA 1 SLOT VỀ 100 ==================
@bot.message_handler(commands=['resetcanva1'])
def admin_reset_canva1slot(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng lệnh này!")

    # Reset stock Canva 1 Slot về 100 (bằng cách xóa stock cũ và tạo mới placeholder)
    stocks.update_one(
        {"category": "canva1slot"},
        {"$set": {"accounts": ["Slot sẵn sàng"] * 100}},
        upsert=True
    )

    categories.update_one({"code": "canva1slot"}, {"$set": {"enabled": True}})

    bot.reply_to(message, "✅ Đã reset Canva 1 Slot về **100 slot** và mở bán lại!")

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
