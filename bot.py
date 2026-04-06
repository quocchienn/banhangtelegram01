import telebot
import random
import os
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from payos import PayOS
from payos.types import CreatePaymentLinkRequest, WebhookType, WebhookDataType
from flask import Flask, request, jsonify
import threading
import time
import re
import hashlib
import hmac
import json

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

# Cấu hình webhook URL (Render sẽ tự động gán domain)
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://your-app.onrender.com/webhook')

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

def notify_admin_payment_success(order):
    """Thông báo admin khi có thanh toán thành công"""
    user = get_user(order["user_id"])
    if order["type"] == "deposit":
        text = f"""
✅ **THANH TOÁN NẠP TIỀN THÀNH CÔNG**

Mã đơn: #{order['order_code']}
User ID: `{order['user_id']}`
Tên: {user.get('first_name', 'Không tên')}
Số tiền: **{order['amount']:,}đ**
Đã tự động cộng vào ví!
        """
    else:
        text = f"""
✅ **THANH TOÁN MUA HÀNG THÀNH CÔNG**

Mã đơn: #{order['order_code']}
User ID: `{order['user_id']}`
Tên: {user.get('first_name', 'Không tên')}
Số tiền: **{order['amount']:,}đ**
Đang chờ xử lý giao hàng...
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

@bot.message_handler(commands=['duyetnap'])  # Giữ lại cho trường hợp cần duyệt thủ công
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
        
        # Kiểm tra nếu đơn mua hàng đã thanh toán nhưng chưa giao
        if order.get("status") != "paid":
            return bot.reply_to(message, "❌ Đơn hàng chưa được thanh toán!")
        
        category = order.get("category")
        user_id = order["user_id"]
        
        # Xử lý Canva 1 slot hoặc YouTube 1 slot
        if category in ["canva1slot", "youtube1slot"]:
            # Đã xử lý từ trước khi nhận webhook
            orders.update_one({"order_code": order_code}, {"$set": {"status": "delivered", "delivered_at": datetime.now()}})
            bot.reply_to(message, f"✅ Đã xác nhận giao thành công đơn #{order_code} (đã được xử lý từ webhook)")
            return
        
        # Các sản phẩm thường
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

@bot.message_handler(commands=['setwebhook'])
def admin_set_webhook(message):
    """Lệnh để cập nhật webhook trên PayOS"""
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Chỉ admin mới dùng được!")
    
    try:
        # Cập nhật webhook trên PayOS
        result = payos.payment_requests.update_webhook(webhook_url=WEBHOOK_URL)
        bot.reply_to(message, f"✅ Đã cập nhật webhook thành công!\nURL: {WEBHOOK_URL}")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi cập nhật webhook: {str(e)}")

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

# ================== NẠP TIỀN ==================
def deposit_menu(call):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(telebot.types.InlineKeyboardButton("20.000đ", callback_data="deposit_20000"))
    markup.add(telebot.types.InlineKeyboardButton("50.000đ", callback_data="deposit_50000"))
    markup.add(telebot.types.InlineKeyboardButton("100.000đ", callback_data="deposit_100000"))
    markup.add(telebot.types.InlineKeyboardButton("200.000đ", callback_data="deposit_200000"))
    markup.add(telebot.types.InlineKeyboardButton("500.000đ", callback_data="deposit_500000"))
    markup.add(telebot.types.InlineKeyboardButton("Nhập số khác", callback_data="deposit_custom"))
    bot.send_message(call.message.chat.id, "💳 Chọn số tiền muốn nạp vào ví:", reply_markup=markup)

def handle_deposit_amount(call):
    if call.data == "deposit_custom":
        bot.send_message(call.message.chat.id, "Nhập số tiền muốn nạp (tối thiểu 10.000đ):")
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
        if amount < 10000:
            return bot.reply_to(message, "❌ Số tiền tối thiểu là 10.000đ!")
        if amount > 5000000:
            return bot.reply_to(message, "❌ Số tiền tối đa là 5.000.000đ!")
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

    payment_data = CreatePaymentLinkRequest(
        order_code=order_code,
        amount=amount,
        description=f"Nap tien #{order_code}",
        return_url=f"https://t.me/{bot.get_me().username}",
        cancel_url=f"https://t.me/{bot.get_me().username}"
    )
    payment_link = payos.payment_requests.create(payment_data)

    bot.send_message(chat_id, f"""
💰 **Nạp tiền vào ví**

Mã đơn: #{order_code}
Số tiền: **{amount:,}đ**

🔗 [Thanh toán ngay]({payment_link.checkout_url})

⚠️ Sau khi thanh toán, tiền sẽ **tự động** được cộng vào ví!
    """, parse_mode='Markdown')

# ================== MUA HÀNG ==================
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
Số dư còn lại: {user.get('balance', 0) - price:,}đ
            """)
    else:
        # Tạo đơn PayOS cho sản phẩm thường
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
            description=f"Mua {info['name'][:20]} #{order_code}",
            return_url=f"https://t.me/{bot.get_me().username}",
            cancel_url=f"https://t.me/{bot.get_me().username}"
        )
        payment_link = payos.payment_requests.create(payment_data)
        bot.send_message(call.message.chat.id, f"""
✅ Đơn hàng #{order_code} đã tạo!

💰 Số tiền: {price:,}đ
📦 Sản phẩm: {info['name']}

🔗 [Thanh toán ngay]({payment_link.checkout_url})

⚠️ Sau khi thanh toán, admin sẽ giao hàng tự động!
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

# ================== WEBHOOK XỬ LÝ THANH TOÁN TỰ ĐỘNG ==================
def verify_webhook_signature(data, signature):
    """Xác minh chữ ký webhook từ PayOS"""
    try:
        # Tạo checksum từ data
        checksum_data = json.dumps(data, separators=(',', ':'))
        expected_signature = hmac.new(
            os.getenv('PAYOS_CHECKSUM_KEY').encode('utf-8'),
            checksum_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        print(f"Lỗi xác minh chữ ký: {e}")
        return False

def process_payment_success(data):
    """Xử lý khi thanh toán thành công"""
    try:
        order_code = data.get('orderCode')
        amount = data.get('amount')
        description = data.get('description', '')
        
        if not order_code:
            return False
        
        # Tìm đơn hàng trong database
        order = orders.find_one({"order_code": order_code})
        if not order:
            print(f"Không tìm thấy đơn hàng #{order_code}")
            return False
        
        # Kiểm tra nếu đơn hàng đã được xử lý
        if order.get("status") not in ["pending", "waiting_email", "waiting_admin"]:
            print(f"Đơn hàng #{order_code} đã được xử lý trước đó (status: {order.get('status')})")
            return True
        
        user_id = order["user_id"]
        
        if order["type"] == "deposit":
            # Nạp tiền: cộng trực tiếp vào ví
            update_balance(user_id, amount)
            orders.update_one({"order_code": order_code}, {"$set": {
                "status": "approved", 
                "approved_at": datetime.now(),
                "payment_data": data
            }})
            
            # Thông báo cho user
            try:
                bot.send_message(user_id, f"""
✅ **NẠP TIỀN THÀNH CÔNG!**

Mã đơn: #{order_code}
Số tiền: +{amount:,}đ
Số dư hiện tại: {get_user(user_id)['balance']:,}đ

Cảm ơn bạn đã sử dụng dịch vụ!
                """)
            except Exception as e:
                print(f"Không thể gửi tin nhắn cho user {user_id}: {e}")
            
            # Thông báo admin
            notify_admin_payment_success(order)
            
        elif order["type"] == "purchase":
            # Mua hàng: cập nhật trạng thái đã thanh toán
            orders.update_one({"order_code": order_code}, {"$set": {
                "status": "paid", 
                "paid_at": datetime.now(),
                "payment_data": data
            }})
            
            # Thông báo cho user
            cat_name = CATEGORIES.get(order.get("category"), {}).get("name", "Sản phẩm")
            try:
                bot.send_message(user_id, f"""
✅ **THANH TOÁN THÀNH CÔNG!**

Mã đơn: #{order_code}
Sản phẩm: {cat_name}
Số tiền: {amount:,}đ

🔄 Đơn hàng đang được xử lý, admin sẽ giao hàng trong giây lát!
                """)
            except Exception as e:
                print(f"Không thể gửi tin nhắn cho user {user_id}: {e}")
            
            # Thông báo admin
            notify_admin_payment_success(order)
            
            # TỰ ĐỘNG GIAO HÀNG CHO SẢN PHẨM THƯỜNG (không cần email)
            category = order.get("category")
            if category and category not in ["canva1slot", "youtube1slot"]:
                # Giao hàng tự động
                stock_doc = stocks.find_one({"category": category})
                if stock_doc and stock_doc.get("accounts"):
                    account = stock_doc["accounts"].pop(0)
                    stocks.update_one({"category": category}, {"$set": {"accounts": stock_doc["accounts"]}})
                    
                    orders.update_one({"order_code": order_code}, {"$set": {
                        "status": "delivered", 
                        "delivered_at": datetime.now(),
                        "account": account
                    }})
                    
                    try:
                        bot.send_message(user_id, f"""
🎉 **HÀNG ĐÃ ĐƯỢC GIAO!**

Đơn: #{order_code}
Sản phẩm: {cat_name}
Tài khoản: {account}

Cảm ơn bạn đã mua hàng!
                        """)
                    except Exception as e:
                        print(f"Không thể gửi tin nhắn giao hàng: {e}")
                else:
                    # Hết stock, báo admin
                    try:
                        bot.send_message(ADMIN_ID, f"""
⚠️ **HẾT STOCK!**

Đơn hàng #{order_code} đã được thanh toán nhưng hết stock {cat_name}
User ID: `{user_id}`
Vui lòng xử lý thủ công!
                        """)
                    except:
                        pass
        else:
            # Các loại đơn khác (canva1slot, youtube1slot) - chỉ cập nhật trạng thái đã thanh toán
            orders.update_one({"order_code": order_code}, {"$set": {
                "status": "paid", 
                "paid_at": datetime.now(),
                "payment_data": data
            }})
            
            # Thông báo admin
            notify_admin_payment_success(order)
        
        return True
        
    except Exception as e:
        print(f"Lỗi xử lý webhook: {e}")
        return False

@flask_app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Endpoint nhận callback từ PayOS"""
    try:
        # Lấy dữ liệu từ request
        data = request.get_json()
        signature = request.headers.get('X-PayOS-Signature', '')
        
        print(f"Nhận webhook: {data}")
        
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        # Xác minh chữ ký (tùy chọn, có thể bỏ qua nếu muốn)
        # if not verify_webhook_signature(data, signature):
        #     print("Chữ ký webhook không hợp lệ")
        #     return jsonify({"error": "Invalid signature"}), 401
        
        # Kiểm tra trạng thái thanh toán
        if data.get('status') == 'PAID':
            success = process_payment_success(data)
            if success:
                return jsonify({"success": True}), 200
            else:
                return jsonify({"error": "Cannot process payment"}), 500
        else:
            print(f"Trạng thái thanh toán: {data.get('status')} - Bỏ qua")
            return jsonify({"success": True, "message": "Not paid yet"}), 200
            
    except Exception as e:
        print(f"Lỗi webhook: {e}")
        return jsonify({"error": str(e)}), 500

# ================== FLASK + POLLING ==================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return jsonify({
        "status": "Bot is alive on Render!",
        "webhook_url": WEBHOOK_URL,
        "time": datetime.now().isoformat()
    })

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)
    
    # In thông tin webhook
    print("🤖 Bot đang chạy...")
    print(f"📡 Webhook URL: {WEBHOOK_URL}")
    print("⚡ Thanh toán sẽ được xử lý tự động qua webhook!")
    
    bot.infinity_polling()
