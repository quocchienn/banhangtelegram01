# 🤖 Telegram Shop Bot - Bán Tài Khoản Premium

Bot Telegram chuyên bán các loại tài khoản premium (Hotspot, Gemini, CapCut, Canva, YouTube...) với hệ thống **ví điện tử**, thanh toán PayOS và quản lý stock thông minh.

### Tính năng chính
- Hệ thống ví người dùng (nạp tiền - trừ tiền khi mua)
- Thanh toán qua PayOS
- Quản lý stock tự động (hết hàng sẽ khóa nút mua)
- Upload file TXT để cập nhật kho hàng
- Xử lý đặc biệt cho Canva 1 Slot & YouTube 1 Slot (trừ ví → gửi email → Admin giao thủ công)
- Hệ thống Admin mạnh mẽ

---

## 📋 Danh sách lệnh & chức năng

### 1. Lệnh dành cho Người dùng

| Lệnh / Nút | Mô tả |
|------------|-------|
| `/start` | Hiển thị menu chính, danh sách sản phẩm và nút Ví - Nạp tiền |
| **🛒 Mua [Sản phẩm]** | Mua tài khoản (tự động hoặc qua ví) |
| **💰 Ví của tôi** | Xem thông tin cá nhân: ID, Tên, Số dư, Ngày tham gia |
| **💳 Nạp tiền vào ví** | Nạp tiền vào ví (có nút nhanh 50k, 100k, 200k hoặc nhập số khác, tối thiểu 2.000đ) |

### 2. Lệnh dành cho Admin

| Lệnh | Mô tả |
|------|-------|
| `/users` hoặc `/balance` | Xem danh sách tất cả người dùng và số dư hiện tại |
| `/duyetnap <mã đơn>` | Duyệt đơn nạp tiền (cộng tiền vào ví người dùng) |
| `/giao <mã đơn>` | Giao tài khoản thủ công cho người dùng (dùng cho Canva 1 Slot & YouTube 1 Slot) |
| `/resetbalance <user_id>` | Reset số dư của một người dùng về 0 |
| `/resetallbalance` | Reset số dư của **tất cả** người dùng về 0 (có xác nhận) |
| `/resetcanva1` | Reset kho Canva 1 Slot về **100 slot** |
| `/resetyoutube` | Reset kho YouTube 1 Slot về **10 slot** |

### 3. Upload File TXT (Chỉ Admin)

- Gửi file `.txt` chứa danh sách tài khoản (mỗi dòng 1 tài khoản)
- Bot sẽ **tự động nhận diện** theo tên file (ví dụ: `capcut.txt`, `canva.txt`, `youtube.txt`...)
- Nếu không nhận diện được, bot sẽ hiện nút chọn loại sản phẩm để cập nhật thủ công

---

## 📦 Các sản phẩm hiện có

| Mã sản phẩm     | Tên sản phẩm                  | Giá       | Loại thanh toán          | Stock mặc định |
|-----------------|-------------------------------|-----------|---------------------------|----------------|
| `hotspot`       | Hotspot Shield 7D             | 2.000đ    | Ví hoặc PayOS             | - |
| `gemini`        | Gemini Pro 1 Acc              | 40.000đ   | Ví hoặc PayOS             | - |
| `capcut`        | CapCut Pro 1 Tuần             | 2.000đ    | Ví hoặc PayOS             | - |
| `canva100slot`  | Canva 100 Slot                | 30.000đ   | Ví hoặc PayOS             | - |
| `canva1slot`    | Canva 1 Slot                  | 2.000đ    | **Chỉ qua ví + gửi email** | 100 slot |
| `youtube1slot`  | YouTube 1 Slot                | 2.000đ    | **Chỉ qua ví + gửi email** | 10 slot |

---

## 🔄 Quy trình Canva 1 Slot & YouTube 1 Slot

1. Người dùng bấm mua → Kiểm tra số dư ví
2. Nếu đủ tiền → **Trừ tiền ví ngay lập tức**
3. Bot yêu cầu người dùng gửi **email (@gmail.com)**
4. Người dùng gửi email → Bot tự động chuyển email + thông tin đơn cho Admin
5. Admin kiểm tra và dùng lệnh `/giao <mã đơn>` để giao slot cho người dùng

---

## 🛠 Cấu trúc Database (MongoDB)

- `users` → Thông tin người dùng + số dư
- `orders` → Lịch sử đơn hàng (nạp tiền, mua hàng, trạng thái)
- `stocks` → Kho tài khoản (mảng accounts)
- `categories` → Thông tin các sản phẩm

---

## ⚙️ Cài đặt & Triển khai

### Yêu cầu
- Python 3.8+
- MongoDB Atlas
- Tài khoản PayOS
- Hosting Render.com (khuyến nghị)

### Biến môi trường (.env)

```env
BOT_TOKEN=your_bot_token
PAYOS_CLIENT_ID=your_client_id
PAYOS_API_KEY=your_api_key
PAYOS_CHECKSUM_KEY=your_checksum_key
MONGO_URI=mongodb+srv://...
ADMIN_ID=your_telegram_id
