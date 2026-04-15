# 🤖 Telegram Shop Bot - Bán Tài Khoản Premium

Bot Telegram chuyên bán các loại tài khoản premium (Hotspot, Gemini, CapCut, Canva, YouTube...) với hệ thống **ví điện tử VND & USDT**, thanh toán PayOS, nạp USDT qua Binance và quản lý stock thông minh.

## 🌟 Tính năng chính

- 🌐 **Hỗ trợ đa ngôn ngữ**: Tiếng Việt & English
- 💰 **Hệ thống ví kép**: VND và USDT
- 💳 **Thanh toán PayOS**: Nạp VND qua PayOS
- 💵 **Nạp USDT qua Binance**: Chuyển USDT đến Binance UID của Admin
- 🛒 **Mua hàng tự động**: Trừ tiền ví và giao tài khoản ngay
- 📧 **Xử lý đặc biệt**: Canva 1 Slot & YouTube 1 Slot yêu cầu email
- 📤 **Upload file TXT**: Cập nhật kho hàng nhanh chóng
- 🔧 **Hệ thống Admin mạnh mẽ**: 20+ lệnh quản lý

---

## 📋 Danh sách lệnh & chức năng

### 1. Lệnh dành cho Người dùng

| Lệnh / Nút | Mô tả |
|------------|-------|
| `/start` | Bắt đầu bot, chọn ngôn ngữ và hiển thị menu chính |
| **🌐 Đổi ngôn ngữ** | Chuyển đổi giữa Tiếng Việt và English |
| **💰 Ví của tôi** | Xem thông tin: ID, Tên, Số dư VND, Số dư USDT, Ngày tham gia |
| **💳 Nạp tiền VND** | Nạp VND qua PayOS (50k, 100k, 200k hoặc nhập số khác) |
| **💵 Nạp USDT qua Binance** | Nạp USDT bằng cách chuyển đến Binance UID của Admin |
| **🛒 Mua [Sản phẩm]** | Mua tài khoản (yêu cầu đủ số dư trong ví) |

### 2. Lệnh dành cho Admin

#### 📊 Quản lý User
| Lệnh | Mô tả |
|------|-------|
| `/admin` | Xem danh sách tất cả lệnh admin |
| `/danhsach` | Xem danh sách tất cả người dùng (Tên, ID, Số dư VND/USDT, Ngôn ngữ, Ngày tham gia) |
| `/xoasodu <user_id> [vnd\|usdt\|all]` | Xóa số dư của một người dùng |
| `/xoasoduall [vnd\|usdt\|all]` | Xóa số dư của TẤT CẢ người dùng (có xác nhận) |
| `/addbalance <user_id> <số> [vnd\|usdt]` | Cộng tiền cho người dùng |
| `/resetallbalance` | Reset số dư tất cả user về 0 (có xác nhận) |

#### 💰 Quản lý Nạp tiền
| Lệnh | Mô tả |
|------|-------|
| `/duyetnap <mã đơn>` | Duyệt đơn nạp VND (cộng tiền vào ví) |
| `/duyetnapusdt <mã đơn>` | Duyệt đơn nạp USDT (cộng USDT vào ví) |

#### 📦 Quản lý Đơn hàng
| Lệnh | Mô tả |
|------|-------|
| `/giao <mã đơn>` | Giao tài khoản thủ công (dùng cho Canva/YouTube 1 Slot) |

#### 🔧 Quản lý Stock
| Lệnh | Mô tả |
|------|-------|
| `/stock` | Xem tồn kho hiện tại của tất cả sản phẩm |
| `/setcanva <số>` | Set số lượng Canva 1 Slot (0-999) |
| `/setyoutube <số>` | Set số lượng YouTube 1 Slot (0-999) |
| `/sethotspot <số>` | Set số lượng Hotspot |
| `/setgemini <số>` | Set số lượng Gemini |
| `/setcapcut <số>` | Set số lượng CapCut |
| `/resetcanva1` | Reset Canva 1 Slot về 100 slot (lệnh cũ) |
| `/resetyoutube` | Reset YouTube 1 Slot về 10 slot (lệnh cũ) |

#### 📤 Upload Tài khoản
| Lệnh | Mô tả |
|------|-------|
| `/upload_canva` | Upload file .txt cho Canva 1 Slot |
| `/upload_youtube` | Upload file .txt cho YouTube 1 Slot |
| `/upload_hotspot` | Upload file .txt cho Hotspot |
| `/upload_gemini` | Upload file .txt cho Gemini |
| `/upload_capcut` | Upload file .txt cho CapCut |

#### ⚙️ Cài đặt
| Lệnh | Mô tả |
|------|-------|
| `/setusdtrate <tỷ_giá>` | Cập nhật tỷ giá USDT/VND (mặc định: 27000) |

---

## 📦 Các sản phẩm hiện có

| Mã sản phẩm | Tên sản phẩm | Giá VND | Giá USDT | Loại |
|-------------|--------------|---------|----------|------|
| `hotspot` | Hotspot Shield 7D | 2.000đ | 0.08 USDT | Giao ngay |
| `gemini` | Gemini Pro 1 Acc 26-29D | 40.000đ | 1.6 USDT | Giao ngay |
| `capcut` | CapCut Pro 1 Tuần | 2.000đ | 0.08 USDT | Giao ngay |
| `canva100slot` | Canva 100 Slot | 30.000đ | 1.2 USDT | Giao ngay |
| `canva1slot` | Canva 1 Slot | 2.000đ | 0.08 USDT | **Yêu cầu email** |
| `youtube1slot` | YouTube 1 Slot | 2.000đ | 0.08 USDT | **Yêu cầu email** |

---

## 🔄 Quy trình mua hàng

### Sản phẩm thông thường (Hotspot, Gemini, CapCut, Canva 100 Slot)
1. Người dùng chọn sản phẩm
2. **Kiểm tra số dư ví** → Nếu không đủ: Hiển thị nút nạp tiền
3. Nếu đủ tiền: **Trừ tiền ví ngay lập tức**
4. **Giao tài khoản** cho người dùng

### Sản phẩm Canva 1 Slot & YouTube 1 Slot
1. Người dùng chọn sản phẩm
2. **Kiểm tra số dư ví** → Nếu không đủ: Hiển thị nút nạp tiền
3. Nếu đủ tiền: **Trừ tiền ví ngay lập tức**
4. Bot yêu cầu người dùng gửi **email (@gmail.com)**
5. Người dùng gửi email → Bot chuyển thông tin cho Admin
6. Admin dùng lệnh `/giao <mã đơn>` để giao slot cho người dùng

---

## 💱 Quy trình nạp USDT qua Binance

1. Người dùng chọn **💵 Nạp USDT qua Binance**
2. Nhập số USDT muốn nạp (tối thiểu 1 USDT)
3. Bot hiển thị:
   - Mã đơn hàng
   - Số USDT cần chuyển
   - Binance UID của Admin
   - Ghi chú bắt buộc: `#{mã_đơn}`
4. Người dùng chuyển USDT đến Binance UID
5. Admin kiểm tra và dùng lệnh `/duyetnapusdt <mã_đơn>` để cộng USDT vào ví

---

## 💳 Quy trình nạp VND qua PayOS

1. Người dùng chọn **💳 Nạp tiền VND**
2. Chọn mệnh giá (50k, 100k, 200k) hoặc nhập số khác (tối thiểu 2.000đ)
3. Bot tạo link thanh toán PayOS
4. Người dùng thanh toán qua link
5. Admin kiểm tra và dùng lệnh `/duyetnap <mã_đơn>` để cộng tiền vào ví

---

## 📤 Upload File TXT (Chỉ Admin)

### Cách sử dụng:
1. Dùng lệnh upload tương ứng (ví dụ: `/upload_hotspot`)
2. Gửi file `.txt` chứa danh sách tài khoản
3. Mỗi dòng là một tài khoản (định dạng: `email|password` hoặc `username|password`)

### Ví dụ file `hotspot.txt`:


user1@gmail.com|password123
user2@gmail.com|pass456
user3@yahoo.com|secret789


---

## 🛠 Cấu trúc Database (MongoDB)

### Collection: `users`
json
{
  "user_id": 123456789,
  "username": "telegram_username",
  "first_name": "Người Dùng",
  "balance": 50000,
  "balance_usdt": 2.5,
  "language": "vi",
  "joined_at": "2024-01-01T00:00:00Z",
  "waiting_email_for": null
}


Collection: orders

json
{
  "order_code": 12345678,
  "user_id": 123456789,
  "type": "purchase",
  "category": "hotspot",
  "amount": 2000,
  "amount_usdt": 0.08,
  "currency_used": "vnd",
  "status": "delivered",
  "account": "user@gmail.com|password",
  "created_at": "2024-01-01T00:00:00Z",
  "delivered_at": "2024-01-01T00:00:01Z"
}


Collection: stocks

json
{
  "category": "hotspot",
  "accounts": [
    "user1@gmail.com|pass1",
    "user2@gmail.com|pass2"
  ]
}


Collection: categories

json
{
  "code": "hotspot",
  "name": "Hotspot Shield 7D",
  "name_en": "Hotspot Shield 7D",
  "price": 2000,
  "price_usdt": 0.08,
  "type": "normal",
  "enabled": true
}


Collection: pending_uploads

json
{
  "user_id": 123456789,
  "category": "hotspot",
  "timestamp": "2024-01-01T00:00:00Z"
}


---

⚙️ Cài đặt & Triển khai

Yêu cầu

· Python 3.8+
· MongoDB Atlas
· Tài khoản PayOS
· Hosting Render.com (khuyến nghị)

Biến môi trường (.env)

env
# Telegram Bot
BOT_TOKEN=your_bot_token_here

# PayOS
PAYOS_CLIENT_ID=your_client_id
PAYOS_API_KEY=your_api_key
PAYOS_CHECKSUM_KEY=your_checksum_key

# MongoDB
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/...

# Admin
ADMIN_ID=your_telegram_user_id
ADMIN_BINANCE_ID=1163285604

# Cài đặt
USDT_RATE=27000
PORT=10000


Cài đặt thư viện

bash
pip install pyTelegramBotAPI python-dotenv pymongo payos flask


Chạy bot (local)

bash
python bot.py


---

🚀 Triển khai trên Render.com

1. Tạo Web Service mới
2. Kết nối với GitHub repository
3. Build Command: pip install -r requirements.txt
4. Start Command: python bot.py
5. Thêm tất cả biến môi trường trong mục Environment Variables

requirements.txt


pyTelegramBotAPI==4.14.0
python-dotenv==1.0.0
pymongo==4.5.0
payos==1.1.0
flask==3.0.0


---

📝 Ghi chú

Mục Giá trị
Tỷ giá USDT mặc định 1 USDT = 27.000đ
Stock mặc định Canva 100 slot
Stock mặc định YouTube 10 slot
Email hợp lệ Chỉ @gmail.com
Nạp VND tối thiểu 2.000đ
Nạp USDT tối thiểu 1 USDT
Hoàn tiền tự động Có (nếu hết hàng khi mua)

---

👑 Lệnh Admin nhanh

# Xem danh sách user
/danhsach

# Xem tồn kho
/stock

# Set số lượng Canva 1 Slot về 50
/setcanva 50

# Set số lượng YouTube 1 Slot về 20
/setyoutube 20

# Set số lượng Hotspot về 100
/sethotspot 100

# Set số lượng Gemini về 50
/setgemini 50

# Set số lượng CapCut về 200
/setcapcut 200

# Cộng 100.000đ cho user 123456789
/addbalance 123456789 100000 vnd

# Cộng 5 USDT cho user 123456789
/addbalance 123456789 5 usdt

# Xóa số dư VND của user 123456789
/xoasodu 123456789 vnd

# Xóa số dư USDT của user 123456789
/xoasodu 123456789 usdt

# Xóa tất cả số dư của user 123456789
/xoasodu 123456789 all

# Xóa tất cả số dư VND của mọi user
/xoasoduall vnd

# Xóa tất cả số dư USDT của mọi user
/xoasoduall usdt

# Xóa toàn bộ số dư của mọi user
/xoasoduall all

# Duyệt nạp VND đơn #12345678
/duyetnap 12345678

# Duyệt nạp USDT đơn #87654321
/duyetnapusdt 87654321

# Giao tài khoản cho đơn #11223344
/giao 11223344

# Cập nhật tỷ giá USDT = 28.000đ
/setusdtrate 28000

# Upload tài khoản Hotspot
/upload_hotspot
# Sau đó gửi file .txt

# Upload tài khoản CapCut
/upload_capcut
# Sau đó gửi file .txt

---

🔄 Sơ đồ luồng hoạt động


┌─────────────────────────────────────────────────────────────────┐
│                         NGƯỜI DÙNG                              │
├─────────────────────────────────────────────────────────────────┤
│  /start ──► Chọn ngôn ngữ ──► Menu chính                        │
│     │                                                           │
│     ├──► Ví của tôi ──► Xem số dư VND & USDT                    │
│     │                                                           │
│     ├──► Nạp VND ──► PayOS ──► Admin duyệt ──► Cộng tiền        │
│     │                                                           │
│     ├──► Nạp USDT ──► Binance ──► Admin duyệt ──► Cộng USDT     │
│     │                                                           │
│     └──► Mua hàng ──► Kiểm tra số dư ──► Trừ tiền ──► Giao hàng │
│                              │                                   │
│                              └──► Không đủ ──► Yêu cầu nạp tiền  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                            ADMIN                                 │
├─────────────────────────────────────────────────────────────────┤
│  /danhsach ──► Xem danh sách user                               │
│  /stock ──► Xem tồn kho                                         │
│  /duyetnap ──► Duyệt nạp VND                                    │
│  /duyetnapusdt ──► Duyệt nạp USDT                               │
│  /giao ──► Giao tài khoản Canva/YouTube                         │
│  /set* ──► Điều chỉnh số lượng stock                            │
│  /upload_* ──► Upload file txt cập nhật kho                     │
│  /xoasodu ──► Xóa số dư user                                    │
│  /addbalance ──► Cộng tiền cho user                             │
└─────────────────────────────────────────────────────────────────┘


---

🐛 Xử lý lỗi thường gặp

Lỗi Nguyên nhân Cách khắc phục
Bot không phản hồi Webhook/Polling lỗi Kiểm tra kết nối internet, restart bot
Không tạo được link PayOS Sai API key Kiểm tra lại PAYOS_* trong .env
Không kết nối MongoDB Sai URI hoặc IP không được whitelist Kiểm tra MONGO_URI, thêm IP vào Atlas
Lệnh admin không hoạt động Sai ADMIN_ID Kiểm tra Telegram ID của bạn
Upload file không được Sai định dạng file Đảm bảo file .txt, UTF-8 encoding
Email không được chấp nhận Sai định dạng Chỉ chấp nhận email @gmail.com

---

📄 License

MIT License - Free to use and modify.

---

🤝 Hỗ trợ

Nếu có vấn đề hoặc cần hỗ trợ, vui lòng liên hệ Admin qua Telegram.
