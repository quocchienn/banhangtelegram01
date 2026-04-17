    """
    
    # Gửi thành nhiều phần nếu quá dài
    if len(help_text) > 4000:
        parts = []
        lines = help_text.split('\n')
        current_part = ""
        
        for line in lines:
            if len(current_part + line + '\n') > 3800:
                parts.append(current_part)
                current_part = line + '\n'
            else:
                current_part += line + '\n'
        
        if current_part:
            parts.append(current_part)
        
        for i, part in enumerate(parts):
            bot.send_message(message.chat.id, part, parse_mode='Markdown')
            time.sleep(0.5)
    else:
        bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['reload'])
def admin_reload(message):
    """Tải lại danh mục sản phẩm từ database"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    reload_categories()
    bot.reply_to(message, "✅ Đã tải lại danh mục sản phẩm từ database!")

@bot.message_handler(commands=['prices'])
def admin_view_prices(message):
    """Xem tất cả giá sản phẩm"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    reload_categories()
    
    text = "💰 **BẢNG GIÁ SẢN PHẨM**\n\n"
    
    for code, info in CATEGORIES.items():
        enabled = "✅" if info.get("enabled", True) else "❌"
        text += f"{enabled} **{code}**\n"
        text += f"   🇻🇳 {info['name']}: **{info['price']:,}đ**\n"
        text += f"   🇬🇧 {info['name_en']}: **{info['price_usdt']} USDT**\n"
        text += f"   📦 Tồn kho: **{get_stock_count(code)}**\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['setprice'])
def admin_set_price(message):
    """Sửa giá sản phẩm"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "Sử dụng: /setprice <mã_sp> <giá_vnd> [giá_usdt]\nVí dụ:\n- /setprice hotspot 5000\n- /setprice gemini 50000 2.0")
            return
        
        code = parts[1].lower()
        price_vnd = int(parts[2])
        price_usdt = float(parts[3]) if len(parts) > 3 else round(price_vnd / USDT_RATE, 2)
        
        if code not in CATEGORIES:
            available = ", ".join(CATEGORIES.keys())
            bot.reply_to(message, f"❌ Mã sản phẩm không hợp lệ!\nCác mã có sẵn: {available}")
            return
        
        # Cập nhật trong database
        categories.update_one(
            {"code": code},
            {"$set": {"price": price_vnd, "price_usdt": price_usdt}},
            upsert=True
        )
        
        # Cập nhật cache
        reload_categories()
        
        info = CATEGORIES[code]
        bot.reply_to(
            message,
            f"✅ Đã cập nhật giá sản phẩm **{info['name']}**\n"
            f"💰 VND: **{price_vnd:,}đ**\n"
            f"💵 USDT: **{price_usdt} USDT**"
        )
        
    except ValueError:
        bot.reply_to(message, "❌ Giá tiền phải là số!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['setenable'])
def admin_set_enable(message):
    """Bật/tắt sản phẩm"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "Sử dụng: /setenable <mã_sp> <on|off>\nVí dụ: /setenable hotspot off")
            return
        
        code = parts[1].lower()
        enable_str = parts[2].lower()
        
        if code not in CATEGORIES:
            available = ", ".join(CATEGORIES.keys())
            bot.reply_to(message, f"❌ Mã sản phẩm không hợp lệ!\nCác mã có sẵn: {available}")
            return
        
        enabled = enable_str in ["on", "true", "1", "yes", "bật"]
        
        # Cập nhật trong database
        categories.update_one(
            {"code": code},
            {"$set": {"enabled": enabled}},
            upsert=True
        )
        
        # Cập nhật cache
        reload_categories()
        
        info = CATEGORIES[code]
        status = "✅ BẬT" if enabled else "❌ TẮT"
        bot.reply_to(message, f"{status} sản phẩm **{info['name']}**")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['broadcast'])
def admin_broadcast(message):
    """Gửi thông báo đến tất cả người dùng"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    try:
        # Lấy nội dung sau lệnh
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /broadcast <nội dung thông báo>")
            return
        
        content = parts[1]
        
        # Lấy tất cả user
        all_users = list(users.find({}))
        total_users = len(all_users)
        
        if total_users == 0:
            bot.reply_to(message, "❌ Chưa có người dùng nào!")
            return
        
        # Tạo markup xác nhận
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            telebot.types.InlineKeyboardButton("✅ GỬI", callback_data="confirm_broadcast"),
            telebot.types.InlineKeyboardButton("❌ HỦY", callback_data="cancel_broadcast")
        )
        
        # Lưu nội dung broadcast tạm thời
        pending_uploads.update_one(
            {"user_id": message.from_user.id},
            {"$set": {
                "action": "broadcast",
                "content": content,
                "timestamp": datetime.now()
            }},
            upsert=True
        )
        
        preview = content[:200] + "..." if len(content) > 200 else content
        bot.reply_to(
            message,
            f"📢 **XÁC NHẬN GỬI THÔNG BÁO**\n\n"
            f"👥 Số người nhận: **{total_users}**\n"
            f"📝 Nội dung:\n{preview}\n\n"
            f"Bạn có chắc chắn muốn gửi?",
            parse_mode='Markdown',
            reply_markup=markup
        )
        
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['broadcastlang'])
def admin_broadcast_lang(message):
    """Gửi thông báo đến người dùng theo ngôn ngữ"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "Sử dụng: /broadcastlang <vi|en> <nội dung>")
            return
        
        lang_filter = parts[1].lower()
        content = parts[2]
        
        if lang_filter not in ["vi", "en"]:
            bot.reply_to(message, "❌ Ngôn ngữ phải là 'vi' hoặc 'en'!")
            return
        
        # Lấy user theo ngôn ngữ
        target_users = list(users.find({"language": lang_filter}))
        total_users = len(target_users)
        
        if total_users == 0:
            bot.reply_to(message, f"❌ Không có người dùng nào sử dụng ngôn ngữ '{lang_filter}'!")
            return
        
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            telebot.types.InlineKeyboardButton("✅ GỬI", callback_data=f"confirm_broadcastlang_{lang_filter}"),
            telebot.types.InlineKeyboardButton("❌ HỦY", callback_data="cancel_broadcast")
        )
        
        pending_uploads.update_one(
            {"user_id": message.from_user.id},
            {"$set": {
                "action": "broadcast_lang",
                "lang": lang_filter,
                "content": content,
                "timestamp": datetime.now()
            }},
            upsert=True
        )
        
        preview = content[:200] + "..." if len(content) > 200 else content
        lang_name = "Tiếng Việt" if lang_filter == "vi" else "English"
        bot.reply_to(
            message,
            f"📢 **XÁC NHẬN GỬI THÔNG BÁO**\n\n"
            f"🌐 Ngôn ngữ: **{lang_name}**\n"
            f"👥 Số người nhận: **{total_users}**\n"
            f"📝 Nội dung:\n{preview}\n\n"
            f"Bạn có chắc chắn muốn gửi?",
            parse_mode='Markdown',
            reply_markup=markup
        )
        
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

def execute_broadcast(chat_id, content, lang_filter=None):
    """Thực hiện gửi thông báo"""
    success = 0
    failed = 0
    
    # Lọc user theo ngôn ngữ nếu có
    if lang_filter:
        target_users = users.find({"language": lang_filter})
    else:
        target_users = users.find({})
    
    for user in target_users:
        try:
            user_id = user.get('user_id')
            if user_id:
                bot.send_message(
                    user_id,
                    f"📢 **THÔNG BÁO TỪ ADMIN**\n\n{content}",
                    parse_mode='Markdown'
                )
                success += 1
                time.sleep(0.05)  # Tránh rate limit
        except Exception as e:
            failed += 1
            print(f"Không thể gửi cho user {user.get('user_id')}: {e}")
    
    bot.send_message(
        chat_id,
        f"✅ **KẾT QUẢ GỬI THÔNG BÁO**\n\n"
        f"✅ Thành công: **{success}**\n"
        f"❌ Thất bại: **{failed}**",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['danhsach'])
def admin_danhsach(message):
    """Xem danh sách tất cả người dùng với Tên, ID, Số dư"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    try:
        all_users = list(users.find())
        
        if not all_users:
            bot.reply_to(message, "📊 Chưa có người dùng nào.")
            return
        
        # Sắp xếp theo số dư VND giảm dần
        all_users.sort(key=lambda x: x.get('balance', 0), reverse=True)
        
        total_users = len(all_users)
        total_balance_vnd = sum(u.get('balance', 0) for u in all_users)
        total_balance_usdt = sum(u.get('balance_usdt', 0) for u in all_users)
        
        # Tạo header
        text = f"📊 **DANH SÁCH NGƯỜI DÙNG**\n"
        text += f"👥 Tổng số: **{total_users}** người dùng\n"
        text += f"💰 Tổng VND: **{total_balance_vnd:,}đ**\n"
        text += f"💵 Tổng USDT: **{total_balance_usdt} USDT**\n"
        text += "──────────────────────────────\n\n"
        
        # Gửi từng phần nếu quá dài
        part = 1
        current_text = text
        
        for idx, u in enumerate(all_users, 1):
            user_id = u.get('user_id', 'N/A')
            first_name = u.get('first_name', 'Không tên')
            username = u.get('username', '')
            balance_vnd = u.get('balance', 0)
            balance_usdt = u.get('balance_usdt', 0)
            lang = u.get('language', 'vi')
            joined = u.get('joined_at', datetime.now()).strftime('%d/%m/%Y')
            
            # Format tên hiển thị
            if username:
                display_name = f"{first_name} (@{username})"
            else:
                display_name = first_name
            
            user_info = f"**{idx}.** {display_name}\n"
            user_info += f"   🆔 `{user_id}`\n"
            user_info += f"   💰 VND: `{balance_vnd:,}đ` | USDT: `{balance_usdt}`\n"
            user_info += f"   🌐 {lang.upper()} | 📅 {joined}\n\n"
            
            # Kiểm tra độ dài, nếu quá 3500 ký tự thì gửi phần hiện tại
            if len(current_text + user_info) > 3500:
                bot.send_message(message.chat.id, current_text, parse_mode='Markdown')
                current_text = f"📊 **DANH SÁCH NGƯỜI DÙNG (Phần {part+1})**\n\n"
                part += 1
            
            current_text += user_info
        
        # Gửi phần còn lại
        if current_text:
            bot.send_message(message.chat.id, current_text, parse_mode='Markdown')
            
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")
        print(f"Lỗi lệnh danhsach: {e}")

@bot.message_handler(commands=['xoasodu'])
def admin_xoa_so_du(message):
    """Xóa số dư của một người dùng (đưa về 0)"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /xoasodu <user_id> [vnd|usdt|all]\nVí dụ:\n- /xoasodu 123456789 vnd (chỉ xóa VND)\n- /xoasodu 123456789 usdt (chỉ xóa USDT)\n- /xoasodu 123456789 all (xóa cả hai)")
            return
        
        user_id = int(parts[1])
        currency = parts[2].lower() if len(parts) > 2 else "all"
        
        user = get_user(user_id)
        if not user:
            bot.reply_to(message, f"❌ Không tìm thấy user với ID `{user_id}`!")
            return
        
        old_vnd = user.get('balance', 0)
        old_usdt = user.get('balance_usdt', 0)
        
        if currency == "vnd":
            if old_vnd == 0:
                bot.reply_to(message, f"ℹ️ User `{user_id}` đã có 0đ VND!")
                return
            update_balance(user_id, -old_vnd, "vnd")
            bot.reply_to(
                message, 
                f"✅ Đã xóa **{old_vnd:,}đ** VND của user `{user_id}`!\n"
                f"👤 {user.get('first_name', 'N/A')}\n"
                f"💰 Số dư VND mới: **0đ**\n"
                f"💵 Số dư USDT giữ nguyên: **{old_usdt} USDT**"
            )
            
        elif currency == "usdt":
            if old_usdt == 0:
                bot.reply_to(message, f"ℹ️ User `{user_id}` đã có 0 USDT!")
                return
            update_balance(user_id, -old_usdt, "usdt")
            bot.reply_to(
                message, 
                f"✅ Đã xóa **{old_usdt} USDT** của user `{user_id}`!\n"
                f"👤 {user.get('first_name', 'N/A')}\n"
                f"💰 Số dư VND giữ nguyên: **{old_vnd:,}đ**\n"
                f"💵 Số dư USDT mới: **0 USDT**"
            )
            
        else:  # all
            if old_vnd == 0 and old_usdt == 0:
                bot.reply_to(message, f"ℹ️ User `{user_id}` đã có 0đ và 0 USDT!")
                return
            
            update_balance(user_id, -old_vnd, "vnd")
            update_balance(user_id, -old_usdt, "usdt")
            bot.reply_to(
                message, 
                f"✅ Đã xóa toàn bộ số dư của user `{user_id}`!\n"
                f"👤 {user.get('first_name', 'N/A')}\n"
                f"💰 VND đã xóa: **{old_vnd:,}đ** → 0đ\n"
                f"💵 USDT đã xóa: **{old_usdt}** → 0 USDT"
            )
            
    except ValueError:
        bot.reply_to(message, "❌ ID người dùng không hợp lệ!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['xoasoduall'])
def admin_xoa_so_du_all(message):
    """Xóa số dư của TẤT CẢ người dùng (có xác nhận)"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    try:
        parts = message.text.split()
        currency = parts[1].lower() if len(parts) > 1 else "all"
        
        if currency not in ["vnd", "usdt", "all"]:
            bot.reply_to(message, "❌ Tham số không hợp lệ! Sử dụng: vnd, usdt, hoặc all")
            return
        
        # Đếm số user sẽ bị ảnh hưởng
        total_users = users.count_documents({})
        
        if currency == "vnd":
            total_balance = sum(u.get('balance', 0) for u in users.find())
            if total_balance == 0:
                bot.reply_to(message, "ℹ️ Tất cả user đã có 0đ VND!")
                return
            confirm_text = f"⚠️ **XÁC NHẬN XÓA TOÀN BỘ SỐ DƯ VND**\n\n👥 Số user bị ảnh hưởng: **{total_users}**\n💰 Tổng VND sẽ xóa: **{total_balance:,}đ**\n\nBạn có chắc chắn muốn xóa?"
        elif currency == "usdt":
            total_balance = sum(u.get('balance_usdt', 0) for u in users.find())
            if total_balance == 0:
                bot.reply_to(message, "ℹ️ Tất cả user đã có 0 USDT!")
                return
            confirm_text = f"⚠️ **XÁC NHẬN XÓA TOÀN BỘ SỐ DƯ USDT**\n\n👥 Số user bị ảnh hưởng: **{total_users}**\n💵 Tổng USDT sẽ xóa: **{total_balance} USDT**\n\nBạn có chắc chắn muốn xóa?"
        else:
            total_vnd = sum(u.get('balance', 0) for u in users.find())
            total_usdt = sum(u.get('balance_usdt', 0) for u in users.find())
            if total_vnd == 0 and total_usdt == 0:
                bot.reply_to(message, "ℹ️ Tất cả user đã có 0đ và 0 USDT!")
                return
            confirm_text = f"⚠️ **XÁC NHẬN XÓA TOÀN BỘ SỐ DƯ (VND + USDT)**\n\n👥 Số user bị ảnh hưởng: **{total_users}**\n💰 Tổng VND sẽ xóa: **{total_vnd:,}đ**\n💵 Tổng USDT sẽ xóa: **{total_usdt} USDT**\n\nBạn có chắc chắn muốn xóa?"
        
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            telebot.types.InlineKeyboardButton("✅ XÁC NHẬN", callback_data=f"confirm_xoasoduall_{currency}"),
            telebot.types.InlineKeyboardButton("❌ HỦY", callback_data="cancel_xoasoduall")
        )
        
        bot.reply_to(message, confirm_text, reply_markup=markup, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=['stock'])
def admin_view_stock(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    text = "📦 **TỒN KHO HIỆN TẠI**\n\n"
    
    for code, info in CATEGORIES.items():
        stock_count = get_stock_count(code)
        name = info["name"]
        enabled = "✅" if info.get("enabled", True) else "❌"
        text += f"{enabled} 📌 {name}: **{stock_count}** tài khoản\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['setcanva'])
def admin_set_canva(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /setcanva <số_lượng>")
            return
        
        count = int(parts[1])
        if count < 0:
            bot.reply_to(message, "❌ Số lượng không được âm!")
            return
        
        accounts = ["Slot sẵn sàng"] * count
        stocks.update_one(
            {"category": "canva1slot"}, 
            {"$set": {"accounts": accounts}}, 
            upsert=True
        )
        bot.reply_to(message, f"✅ Đã set Canva 1 Slot về **{count} slot**!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /setcanva <số_lượng>")

@bot.message_handler(commands=['setyoutube'])
def admin_set_youtube(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /setyoutube <số_lượng>")
            return
        
        count = int(parts[1])
        if count < 0:
            bot.reply_to(message, "❌ Số lượng không được âm!")
            return
        
        accounts = ["Slot sẵn sàng"] * count
        stocks.update_one(
            {"category": "youtube1slot"}, 
            {"$set": {"accounts": accounts}}, 
            upsert=True
        )
        bot.reply_to(message, f"✅ Đã set YouTube 1 Slot về **{count} slot**!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /setyoutube <số_lượng>")

@bot.message_handler(commands=['sethotspot'])
def admin_set_hotspot(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /sethotspot <số_lượng>")
            return
        
        count = int(parts[1])
        if count < 0:
            bot.reply_to(message, "❌ Số lượng không được âm!")
            return
        
        accounts = ["Slot sẵn sàng"] * count
        stocks.update_one(
            {"category": "hotspot"}, 
            {"$set": {"accounts": accounts}}, 
            upsert=True
        )
        bot.reply_to(message, f"✅ Đã set Hotspot về **{count} tài khoản**!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /sethotspot <số_lượng>")

@bot.message_handler(commands=['setgemini'])
def admin_set_gemini(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /setgemini <số_lượng>")
            return
        
        count = int(parts[1])
        if count < 0:
            bot.reply_to(message, "❌ Số lượng không được âm!")
            return
        
        accounts = ["Slot sẵn sàng"] * count
        stocks.update_one(
            {"category": "gemini"}, 
            {"$set": {"accounts": accounts}}, 
            upsert=True
        )
        bot.reply_to(message, f"✅ Đã set Gemini về **{count} tài khoản**!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /setgemini <số_lượng>")

@bot.message_handler(commands=['setcapcut'])
def admin_set_capcut(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /setcapcut <số_lượng>")
            return
        
        count = int(parts[1])
        if count < 0:
            bot.reply_to(message, "❌ Số lượng không được âm!")
            return
        
        accounts = ["Slot sẵn sàng"] * count
        stocks.update_one(
            {"category": "capcut"}, 
            {"$set": {"accounts": accounts}}, 
            upsert=True
        )
        bot.reply_to(message, f"✅ Đã set CapCut về **{count} tài khoản**!")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /setcapcut <số_lượng>")

@bot.message_handler(commands=['resetcanva1'])
def admin_reset_canva1(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    stocks.update_one({"category": "canva1slot"}, {"$set": {"accounts": ["Slot sẵn sàng"] * 100}}, upsert=True)
    bot.reply_to(message, "✅ Đã reset Canva 1 Slot về **100 slot**!")

@bot.message_handler(commands=['resetyoutube'])
def admin_reset_youtube(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    stocks.update_one({"category": "youtube1slot"}, {"$set": {"accounts": ["Slot sẵn sàng"] * 10}}, upsert=True)
    bot.reply_to(message, "✅ Đã reset YouTube 1 Slot về **10 slot**!")

# ================== UPLOAD FILE TXT ==================
@bot.message_handler(commands=['upload_canva', 'upload_youtube', 'upload_hotspot', 'upload_gemini', 'upload_capcut'])
def admin_upload_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    cmd = message.text.split()[0].split('_')[1]
    
    category_map = {
        "canva": "canva1slot",
        "youtube": "youtube1slot",
        "hotspot": "hotspot",
        "gemini": "gemini",
        "capcut": "capcut"
    }
    
    category = category_map.get(cmd)
    if not category:
        return
    
    pending_uploads.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"category": category, "timestamp": datetime.now(), "action": "upload"}},
        upsert=True
    )
    
    product_name = CATEGORIES[category]["name"]
    bot.reply_to(
        message, 
        f"📤 Vui lòng gửi file .txt chứa danh sách tài khoản cho **{product_name}**\n"
        f"Mỗi dòng là một tài khoản (định dạng: `email|password` hoặc `username|password` hoặc tài khoản đơn)"
    )

@bot.message_handler(commands=['duyetnap'])
def admin_duyet_nap(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /duyetnap <mã đơn>")
            return
        
        order_code = int(parts[1])
        order = orders.find_one({"order_code": order_code, "type": "deposit", "status": "pending"})
        if not order:
            bot.reply_to(message, "❌ Không tìm thấy đơn nạp pending!")
            return
        
        user_id = order['user_id']
        amount = order['amount']
        update_balance(user_id, amount)
        orders.update_one({"order_code": order_code}, {"$set": {"status": "approved", "approved_at": datetime.now()}})
        
        user = get_user(user_id)
        lang = user.get("language", "vi")
        if lang == "vi":
            msg = f"✅ Nạp tiền đã được duyệt!\nSố tiền: +{amount:,}đ\nSố dư hiện tại: {get_user(user_id)['balance']:,}đ"
        else:
            msg = f"✅ Deposit approved!\nAmount: +{amount:,} VND\nCurrent balance: {get_user(user_id)['balance']:,} VND"
        
        bot.send_message(user_id, msg)
        bot.reply_to(message, f"✅ Đã duyệt nạp tiền #{order_code} - Cộng {amount:,}đ cho user {user_id}")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /duyetnap <mã đơn>")

@bot.message_handler(commands=['duyetnapusdt'])
def admin_duyet_nap_usdt(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /duyetnapusdt <mã đơn>")
            return
        
        order_code = int(parts[1])
        order = orders.find_one({"order_code": order_code, "type": "deposit_usdt", "status": "pending"})
        if not order:
            bot.reply_to(message, "❌ Không tìm thấy đơn nạp USDT pending!")
            return
        
        user_id = order['user_id']
        amount_usdt = order['amount_usdt']
        
        update_balance(user_id, amount_usdt, "usdt")
        orders.update_one({"order_code": order_code}, {"$set": {"status": "approved", "approved_at": datetime.now()}})
        
        user = get_user(user_id)
        lang = user.get("language", "vi")
        if lang == "vi":
            msg = f"✅ Nạp USDT đã được duyệt!\nSố tiền: +{amount_usdt} USDT\nSố dư USDT hiện tại: {get_user(user_id)['balance_usdt']} USDT"
        else:
            msg = f"✅ USDT deposit approved!\nAmount: +{amount_usdt} USDT\nCurrent USDT balance: {get_user(user_id)['balance_usdt']} USDT"
        
        bot.send_message(user_id, msg)
        bot.reply_to(message, f"✅ Đã duyệt nạp USDT #{order_code} - Cộng {amount_usdt} USDT cho user {user_id}")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /duyetnapusdt <mã đơn>")

@bot.message_handler(commands=['giao'])
def admin_giao(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /giao <mã đơn>")
            return
        
        order_code = int(parts[1])
        order = orders.find_one({"order_code": order_code})
        if not order:
            bot.reply_to(message, "❌ Không tìm thấy đơn!")
            return
        
        category = order.get("category")
        user_id = order["user_id"]
        stock_doc = stocks.find_one({"category": category})
        
        if not stock_doc or not stock_doc.get("accounts"):
            bot.reply_to(message, "❌ Hết stock loại này!")
            return
        
        account = stock_doc["accounts"].pop(0)
        stocks.update_one({"category": category}, {"$set": {"accounts": stock_doc["accounts"]}})
        
        user = get_user(user_id)
        lang = user.get("language", "vi")
        product_name = CATEGORIES.get(category, {}).get("name" if lang == "vi" else "name_en", category)
        
        if lang == "vi":
            msg = f"""
🎉 **Tài khoản đã được giao!**

Đơn: #{order_code}
Sản phẩm: {product_name}
Tài khoản: `{account}`
            """
        else:
            msg = f"""
🎉 **Account delivered!**

Order: #{order_code}
Product: {product_name}
Account: `{account}`
            """
        bot.send_message(user_id, msg, parse_mode='Markdown')
        orders.update_one({"order_code": order_code}, {"$set": {"status": "delivered", "delivered_at": datetime.now(), "account": account}})
        bot.reply_to(message, f"✅ Đã giao thành công đơn #{order_code}")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /giao <mã đơn>")

@bot.message_handler(commands=['addbalance'])
def admin_add_balance(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "Sử dụng: /addbalance <user_id> <số_tiền> [vnd|usdt]")
            return
        
        user_id = int(parts[1])
        amount = float(parts[2]) if '.' in parts[2] else int(parts[2])
        currency = parts[3].lower() if len(parts) > 3 else "vnd"
        
        if currency not in ["vnd", "usdt"]:
            bot.reply_to(message, "Currency phải là 'vnd' hoặc 'usdt'")
            return
        
        update_balance(user_id, amount, currency)
        
        user = get_user(user_id)
        if currency == "vnd":
            bot.reply_to(message, f"✅ Đã cộng {amount:,}đ cho user {user_id}\nSố dư mới: {user['balance']:,}đ")
        else:
            bot.reply_to(message, f"✅ Đã cộng {amount} USDT cho user {user_id}\nSố dư mới: {user['balance_usdt']} USDT")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /addbalance <user_id> <số_tiền> [vnd|usdt]")

@bot.message_handler(commands=['resetallbalance'])
def admin_reset_all_balance(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ Xác nhận reset tất cả", callback_data="confirm_reset_all"))
    markup.add(telebot.types.InlineKeyboardButton("❌ Hủy", callback_data="cancel_reset_all"))
    bot.reply_to(message, "⚠️ Bạn sắp reset số dư về 0 cho **TẤT CẢ** user (cả VND và USDT). Xác nhận?", reply_markup=markup)

@bot.message_handler(commands=['setusdtrate'])
def admin_set_usdt_rate(message):
    global USDT_RATE
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Sử dụng: /setusdtrate <tỷ_giá>")
            return
        
        new_rate = int(parts[1])
        USDT_RATE = new_rate
        bot.reply_to(message, f"✅ Đã cập nhật tỷ giá: 1 USDT = {new_rate:,}đ")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}\nSử dụng: /setusdtrate <tỷ_giá>")

# ================== HANDLER CHO DOCUMENT (FILE UPLOAD) ==================
@bot.message_handler(content_types=['document'])
def handle_document(message):
    # Chỉ admin mới được upload
    if message.from_user.id != ADMIN_ID:
        return
    
    pending = pending_uploads.find_one({"user_id": message.from_user.id})
    if not pending:
        return
    
    action = pending.get("action", "upload")
    if action != "upload":
        return
    
    category = pending.get("category")
    if not category:
        return
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        content = downloaded_file.decode('utf-8')
        accounts = [line.strip() for line in content.split('\n') if line.strip()]
        
        if not accounts:
            bot.reply_to(message, "❌ File trống hoặc không có tài khoản hợp lệ!")
            return
        
        stock_doc = stocks.find_one({"category": category})
        if stock_doc:
            existing_accounts = stock_doc.get("accounts", [])
            existing_accounts.extend(accounts)
            stocks.update_one(
                {"category": category},
                {"$set": {"accounts": existing_accounts}}
            )
        else:
            stocks.insert_one({"category": category, "accounts": accounts})
        
        pending_uploads.delete_one({"user_id": message.from_user.id})
        
        product_name = CATEGORIES[category]["name"]
        bot.reply_to(
            message, 
            f"✅ Đã thêm **{len(accounts)}** tài khoản vào **{product_name}**!\n"
            f"Tổng số tài khoản hiện tại: **{get_stock_count(category)}**"
        )
        
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi khi xử lý file: {str(e)}")

# ================== CALLBACK HANDLER ==================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    try:
        if call.data.startswith("lang_"):
            handle_language_selection(call)
        elif call.data == "change_language":
            change_language_menu(call)
        elif call.data == "my_wallet":
            show_wallet(call)
        elif call.data == "deposit":
            deposit_menu(call)
        elif call.data == "deposit_usdt":
            deposit_usdt_prompt(call)
        elif call.data == "back_to_menu":
            show_main_menu(call.message.chat.id, call.from_user.id, call.from_user.first_name)
        elif call.data == "refresh_menu":
            # Làm mới menu - edit message hiện tại
            reload_categories()
            show_main_menu(call.message.chat.id, call.from_user.id, call.from_user.first_name, call.message.message_id)
        elif call.data.startswith("deposit_"):
            handle_deposit_amount(call)
        elif call.data.startswith("buy_"):
            handle_buy(call)
        elif call.data == "outofstock":
            lang = get_lang(call.from_user.id)
            bot.send_message(call.message.chat.id, 
                "❌ Sản phẩm hiện đang hết hàng!" if lang == "vi" else "❌ Product is out of stock!")
        elif call.data in ["confirm_reset_all", "cancel_reset_all"]:
            handle_reset_all(call)
        elif call.data.startswith("confirm_xoasoduall_"):
            handle_xoasoduall_callback(call)
        elif call.data == "cancel_xoasoduall":
            bot.edit_message_text("❌ Đã hủy thao tác xóa số dư.", call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id, "Đã hủy")
        elif call.data == "confirm_broadcast":
            handle_broadcast_confirm(call)
        elif call.data.startswith("confirm_broadcastlang_"):
            handle_broadcastlang_confirm(call)
        elif call.data == "cancel_broadcast":
            bot.edit_message_text("❌ Đã hủy gửi thông báo.", call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id, "Đã hủy")
            pending_uploads.delete_one({"user_id": call.from_user.id})
    except Exception as e:
        print("Lỗi callback:", e)

def handle_broadcast_confirm(call):
    """Xác nhận gửi broadcast"""
    if call.from_user.id != ADMIN_ID:
        return
    
    pending = pending_uploads.find_one({"user_id": call.from_user.id})
    if not pending:
        bot.edit_message_text("❌ Không tìm thấy nội dung thông báo!", call.message.chat.id, call.message.message_id)
        return
    
    content = pending.get("content", "")
    if not content:
        bot.edit_message_text("❌ Nội dung trống!", call.message.chat.id, call.message.message_id)
        return
    
    bot.edit_message_text("📤 **Đang gửi thông báo...**", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    
    # Thực hiện gửi trong thread riêng để không block
    def do_broadcast():
        execute_broadcast(call.message.chat.id, content)
    
    threading.Thread(target=do_broadcast).start()
    
    pending_uploads.delete_one({"user_id": call.from_user.id})

def handle_broadcastlang_confirm(call):
    """Xác nhận gửi broadcast theo ngôn ngữ"""
    if call.from_user.id != ADMIN_ID:
        return
    
    lang_filter = call.data.replace("confirm_broadcastlang_", "")
    
    pending = pending_uploads.find_one({"user_id": call.from_user.id})
    if not pending:
        bot.edit_message_text("❌ Không tìm thấy nội dung thông báo!", call.message.chat.id, call.message.message_id)
        return
    
    content = pending.get("content", "")
    if not content:
        bot.edit_message_text("❌ Nội dung trống!", call.message.chat.id, call.message.message_id)
        return
    
    bot.edit_message_text("📤 **Đang gửi thông báo...**", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    
    # Thực hiện gửi trong thread riêng
    def do_broadcast():
        execute_broadcast(call.message.chat.id, content, lang_filter)
    
    threading.Thread(target=do_broadcast).start()
    
    pending_uploads.delete_one({"user_id": call.from_user.id})

def handle_reset_all(call):
    if call.from_user.id != ADMIN_ID:
        return
    if call.data == "cancel_reset_all":
        bot.edit_message_text("Đã hủy.", call.message.chat.id, call.message.message_id)
        return
    users.update_many({}, {"$set": {"balance": 0, "balance_usdt": 0}})
    bot.edit_message_text("✅ Đã reset số dư về 0 cho tất cả user.", call.message.chat.id, call.message.message_id)

def handle_xoasoduall_callback(call):
    """Xử lý callback xác nhận xóa số dư tất cả user"""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Bạn không có quyền!", show_alert=True)
        return
    
    currency = call.data.replace("confirm_xoasoduall_", "")
    
    # Đếm và tính tổng trước khi xóa
    total_users = users.count_documents({})
    total_vnd = sum(u.get('balance', 0) for u in users.find())
    total_usdt = sum(u.get('balance_usdt', 0) for u in users.find())
    
    # Thực hiện xóa
    if currency == "vnd":
        users.update_many({}, {"$set": {"balance": 0}})
        result_text = f"✅ **ĐÃ XÓA TOÀN BỘ SỐ DƯ VND**\n\n👥 Đã xử lý: **{total_users}** user\n💰 Đã xóa: **{total_vnd:,}đ**"
    elif currency == "usdt":
        users.update_many({}, {"$set": {"balance_usdt": 0}})
        result_text = f"✅ **ĐÃ XÓA TOÀN BỘ SỐ DƯ USDT**\n\n👥 Đã xử lý: **{total_users}** user\n💵 Đã xóa: **{total_usdt} USDT**"
    else:  # all
        users.update_many({}, {"$set": {"balance": 0, "balance_usdt": 0}})
        result_text = f"✅ **ĐÃ XÓA TOÀN BỘ SỐ DƯ (VND + USDT)**\n\n👥 Đã xử lý: **{total_users}** user\n💰 Đã xóa VND: **{total_vnd:,}đ**\n💵 Đã xóa USDT: **{total_usdt} USDT**"
    
    bot.edit_message_text(result_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    bot.answer_callback_query(call.id, "✅ Đã xóa thành công!")

# ================== XỬ LÝ TIN NHẮN THÔNG THƯỜNG (CUỐI CÙNG) ==================
@bot.message_handler(func=lambda m: True)
def handle_user_message(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    # Bỏ qua nếu là lệnh (bắt đầu bằng /)
    if message.text and message.text.startswith('/'):
        lang = user.get("language", "vi")
        if lang == "vi":
            bot.reply_to(message, "❌ Lệnh không tồn tại. Dùng /help để xem hướng dẫn.")
        else:
            bot.reply_to(message, "❌ Command not found. Use /help for guidance.")
        return
    
    waiting_for = user.get("waiting_email_for")
    
    if waiting_for:
        email = message.text.strip()
        lang = user.get("language", "vi")
        
        if not re.match(r'^[\w\.-]+@gmail\.com$', email, re.IGNORECASE):
            bot.reply_to(message, t(user_id, 'email_invalid'))
            return
        
        pending = orders.find_one({"order_code": waiting_for, "user_id": user_id, "status": "waiting_email"})
        
        if pending:
            category = pending.get('category')
            product_name = CATEGORIES.get(category, {}).get("name" if lang == "vi" else "name_en", "1 Slot")
            
            bot.send_message(ADMIN_ID, f"""
📨 **YÊU CẦU THÊM {product_name} / REQUEST FOR {product_name}**

Mã đơn/Order: #{pending['order_code']}
User ID: `{user_id}`
Tên/Name: {message.from_user.first_name or 'N/A'}
Email: `{email}`
Ngôn ngữ/Language: {lang.upper()}
            """)
            
            orders.update_one(
                {"_id": pending["_id"]}, 
                {"$set": {"status": "waiting_admin", "user_email": email}}
            )
            
            users.update_one(
                {"user_id": user_id}, 
                {"$set": {"waiting_email_for": None}}
            )
            
            bot.reply_to(message, t(user_id, 'email_sent'))
        else:
            users.update_one(
                {"user_id": user_id}, 
                {"$set": {"waiting_email_for": None}}
            )
            bot.reply_to(message, "❌ Không tìm thấy đơn hàng. Vui lòng dùng /start để bắt đầu lại.")
        
        return
    
    # Tin nhắn thông thường không phải lệnh
    lang = user.get("language", "vi")
    if lang == "vi":
        bot.reply_to(message, "❌ Không hiểu lệnh. Dùng /help để xem hướng dẫn.")
    else:
        bot.reply_to(message, "❌ Command not understood. Use /help for guidance.")

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
    print(f"📊 Tỷ giá USDT: 1 USDT = {USDT_RATE:,}đ")
    print(f"👑 Admin Binance ID: {ADMIN_BINANCE_ID}")
    print(f"🆔 Admin Telegram ID: {ADMIN_ID}")
    print(f"📝 Lệnh admin: /admin, /a, /helpadmin")
    bot.infinity_polling()
