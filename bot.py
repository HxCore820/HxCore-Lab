"""
🤖 Zun AI Bot - Telegram AI Hub
Ngày sinh: 1/1/2026
Tác giả: Zun Team
"""

import os
import telebot
from telebot import types
import google.generativeai as genai
import json
from datetime import datetime, timedelta
import re

# ============ FIREBASE SETUP (EMBEDDED) ============
import firebase_admin
from firebase_admin import credentials, firestore

def init_firebase():
    """Khởi tạo Firebase từ GitHub Secrets"""
    try:
        cred_json = os.getenv("FIREBASE_CREDENTIALS")
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        print(f"⚠️ Firebase init error: {e}")
        return None

db = init_firebase()

# ============ CẤU HÌNH BOT ============
BOT_NAME = "Zun"
BOT_BIRTHDAY = "1/1/2026"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Cấu hình Gemini AI - SỬ DỤNG MODEL GIỐNG BẠN
genai.configure(api_key=GEMINI_KEY)
MODEL_NAME = 'gemini-flash-latest'  # Giống bản gốc của bạn
model = genai.GenerativeModel(MODEL_NAME)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============ HỆ THỐNG ĐIỂM ============
INITIAL_POINTS = 100  # Điểm khi liên kết bot
QUESTION_COST = 0.5   # Giá mỗi câu hỏi
RESET_DAYS = 7        # Reset điểm sau 7 ngày

# ============ DATABASE FUNCTIONS ============
def get_user_data(user_id):
    """Lấy dữ liệu user từ Firebase"""
    if not db:
        return {'points': 999, 'linked_bots': [], 'total_questions': 0, 'last_reset': datetime.now()}
    
    doc = db.collection('users').document(str(user_id)).get()
    if doc.exists:
        return doc.to_dict()
    else:
        # Tạo user mới
        new_user = {
            'points': 0,
            'linked_bots': [],
            'last_reset': datetime.now(),
            'total_questions': 0,
            'join_date': datetime.now()
        }
        db.collection('users').document(str(user_id)).set(new_user)
        return new_user

def update_points(user_id, points_change):
    """Cập nhật điểm"""
    if not db:
        return 999
    
    user_ref = db.collection('users').document(str(user_id))
    user_data = get_user_data(user_id)
    
    new_points = user_data['points'] + points_change
    user_ref.update({
        'points': new_points,
        'total_questions': user_data.get('total_questions', 0) + 1
    })
    return new_points

def check_reset_points(user_id):
    """Kiểm tra reset điểm hàng tuần"""
    if not db:
        return False
    
    user_data = get_user_data(user_id)
    last_reset = user_data.get('last_reset')
    
    if isinstance(last_reset, str):
        last_reset = datetime.fromisoformat(last_reset)
    
    # Nếu quá 7 ngày thì reset
    if datetime.now() - last_reset > timedelta(days=RESET_DAYS):
        linked_count = len(user_data.get('linked_bots', []))
        points_add = linked_count * INITIAL_POINTS
        
        db.collection('users').document(str(user_id)).update({
            'points': user_data['points'] + points_add,
            'last_reset': datetime.now()
        })
        return True
    return False

def link_new_bot(user_id, bot_token):
    """Liên kết bot mới"""
    if not db:
        return False, "❌ Firebase chưa kết nối!"
    
    try:
        # Test token
        test_bot = telebot.TeleBot(bot_token)
        bot_info = test_bot.get_me()
        
        user_ref = db.collection('users').document(str(user_id))
        user_data = get_user_data(user_id)
        linked_bots = user_data.get('linked_bots', [])
        
        # Kiểm tra đã liên kết chưa
        if bot_token in linked_bots:
            return False, "❌ Bot này đã được liên kết rồi!"
        
        # Thêm bot
        linked_bots.append(bot_token)
        user_ref.update({
            'linked_bots': linked_bots,
            'points': user_data['points'] + INITIAL_POINTS
        })
        
        # Lưu thông tin bot
        db.collection('linked_bots').document(bot_token).set({
            'owner_id': user_id,
            'bot_username': bot_info.username,
            'bot_name': bot_info.first_name,
            'linked_at': datetime.now()
        })
        
        return True, f"✅ Liên kết thành công @{bot_info.username}\n💰 +{INITIAL_POINTS} điểm!"
        
    except Exception as e:
        return False, f"❌ Token không hợp lệ!\n{str(e)}"

# ============ KEYBOARD ============
def main_menu():
    """Menu chính"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("💬 Chat với Zun"),
        types.KeyboardButton("🔗 Liên kết Bot"),
        types.KeyboardButton("💰 Điểm của tôi"),
        types.KeyboardButton("📊 Thống kê"),
        types.KeyboardButton("❓ Trợ giúp"),
        types.KeyboardButton("👤 Về Zun")
    )
    return markup

# ============ BOT HANDLERS ============
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    get_user_data(user_id)  # Tạo user
    
    welcome = f"""
👋 Xin chào {user_name}!

🤖 Tôi là **{BOT_NAME}** - Sinh ngày {BOT_BIRTHDAY}
💼 AI Hub hỗ trợ bot Telegram

**✨ Tính năng:**
• 💬 Trò chuyện AI thông minh
• 🔗 Liên kết bot nhận 100 điểm
• 💰 0.5 điểm/câu hỏi
• 🔄 Reset điểm mỗi 7 ngày

👇 Chọn chức năng bên dưới!
    """
    
    bot.send_message(message.chat.id, welcome, 
                    parse_mode='Markdown',
                    reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "👤 Về Zun")
def about_zun(message):
    about = f"""
🤖 **Thông tin về {BOT_NAME}**

📅 Ngày sinh: {BOT_BIRTHDAY}
🎯 Nhiệm vụ: Hỗ trợ AI cho bot Telegram
🧠 AI Engine: Google Gemini Flash Latest
💾 Database: Firebase Firestore

**📌 Đặc điểm:**
• Thông minh, nhanh nhạy
• Trả lời chuyên nghiệp
• Hỗ trợ đa dạng chủ đề
• Nghiêm túc trong công việc

**💡 Triết lý:**
"Công nghệ phục vụ con người,
AI giúp đời sống dễ dàng hơn"

Made with ❤️ by Zun Team
    """
    bot.send_message(message.chat.id, about, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💰 Điểm của tôi")
def check_points(message):
    user_id = message.from_user.id
    check_reset_points(user_id)
    user_data = get_user_data(user_id)
    
    points = user_data['points']
    linked = len(user_data.get('linked_bots', []))
    questions = user_data.get('total_questions', 0)
    
    # Tính số câu hỏi còn lại
    remaining_q = int(points / QUESTION_COST)
    
    # Tạo nút inline
    markup = types.InlineKeyboardMarkup()
    if linked == 0:
        markup.add(types.InlineKeyboardButton("🔗 Liên kết Bot ngay", callback_data="link_guide"))
    
    msg = f"""
💳 **Thông tin điểm của bạn**

💰 Số dư: **{points:.1f}** điểm
🔗 Bot liên kết: **{linked}** bot
❓ Đã hỏi: **{questions}** câu
📊 Còn lại: **~{remaining_q}** câu

{'⚠️ Hết điểm rồi! Liên kết bot để có điểm.' if points < QUESTION_COST else '✅ Còn đủ điểm để chat!'}
    """
    
    bot.send_message(message.chat.id, msg, 
                    parse_mode='Markdown',
                    reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🔗 Liên kết Bot")
def link_guide(message):
    guide = """
🔗 **Hướng dẫn liên kết Bot**

**Bước 1:** Tạo bot với @BotFather
**Bước 2:** Copy token bot (dạng: `123456:ABC-DEF...`)
**Bước 3:** Gửi lệnh cho tôi:

`/link YOUR_BOT_TOKEN`

**Ví dụ:**
`/link 7362817362:AAHfG7shdgJShs_jshdjJHDjs`

✅ Thành công → +100 điểm
🔄 Reset mỗi tuần
    """
    bot.send_message(message.chat.id, guide, parse_mode='Markdown')

@bot.message_handler(commands=['link'])
def link_bot_token(message):
    user_id = message.from_user.id
    
    # Lấy token
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❌ Thiếu token!\nDùng: `/link TOKEN`", parse_mode='Markdown')
        return
    
    token = parts[1].strip()
    
    # Validate token format
    if not re.match(r'^\d+:[A-Za-z0-9_-]+$', token):
        bot.reply_to(message, "❌ Token không đúng format!")
        return
    
    bot.send_chat_action(message.chat.id, 'typing')
    success, msg = link_new_bot(user_id, token)
    
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📊 Thống kê")
def stats(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    
    linked_bots = user_data.get('linked_bots', [])
    
    if not linked_bots:
        bot.send_message(message.chat.id, 
            "📊 Bạn chưa liên kết bot nào!\n\n"
            "🔗 Liên kết ngay để nhận 100 điểm.",
            reply_markup=main_menu())
        return
    
    bot_list = "**🤖 Danh sách bot:**\n\n"
    
    for i, token in enumerate(linked_bots, 1):
        if db:
            bot_doc = db.collection('linked_bots').document(token).get()
            if bot_doc.exists:
                info = bot_doc.to_dict()
                username = info.get('bot_username', 'Unknown')
                bot_list += f"{i}. @{username}\n"
            else:
                bot_list += f"{i}. Bot #{i}\n"
        else:
            bot_list += f"{i}. Bot #{i}\n"
    
    msg = f"""
📊 **Thống kê chi tiết**

{bot_list}

💰 Tổng điểm: {user_data['points']:.1f}
❓ Tổng câu hỏi: {user_data.get('total_questions', 0)}
🔗 Tổng bot: {len(linked_bots)}
    """
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "❓ Trợ giúp")
def help_msg(message):
    help_text = f"""
❓ **Hướng dẫn sử dụng {BOT_NAME}**

**1️⃣ Liên kết Bot (nhận 100đ)**
   `/link TOKEN` - Liên kết bot mới
   
**2️⃣ Chat với AI (0.5đ/câu)**
   Chọn "💬 Chat với Zun" hoặc gửi tin nhắn trực tiếp
   
**3️⃣ Kiểm tra điểm**
   "💰 Điểm của tôi" - Xem số dư
   
**4️⃣ Xem thống kê**
   "📊 Thống kê" - Chi tiết bot đã liên kết

**📌 Lưu ý:**
• Hết điểm = không chat được
• Reset điểm mỗi 7 ngày
• Liên kết nhiều bot = nhiều điểm

**🆘 Cần hỗ trợ?**
Liên hệ admin hoặc báo lỗi qua GitHub
    """
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "💬 Chat với Zun")
def chat_mode(message):
    bot.send_message(message.chat.id,
        f"💬 **Chế độ chat kích hoạt!**\n\n"
        f"Tôi là {BOT_NAME}, sẵn sàng trả lời mọi câu hỏi của bạn! 😊\n\n"
        f"Hãy gửi câu hỏi ngay nhé! 👇",
        parse_mode='Markdown')

# ============ CHAT AI (GIỐNG BẢN GỐC CỦA BẠN) ============
@bot.message_handler(func=lambda m: True)
def chat_ai(message):
    user_id = message.from_user.id
    
    # Check reset
    check_reset_points(user_id)
    
    # Kiểm tra điểm
    user_data = get_user_data(user_id)
    if user_data['points'] < QUESTION_COST:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 Liên kết Bot", callback_data="link_guide"))
        
        bot.reply_to(message,
            "❌ **Hết điểm rồi!**\n\n"
            "💡 Liên kết bot để nhận 100 điểm:\n"
            "`/link YOUR_BOT_TOKEN`",
            parse_mode='Markdown',
            reply_markup=markup)
        return
    
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Gửi tin nhắn đến Gemini (GIỐNG BẢN GỐC)
        response = model.generate_content(message.text)
        
        if response.text:
            # Trừ điểm
            new_points = update_points(user_id, -QUESTION_COST)
            
            # Trả lời
            reply = f"{response.text}\n\n_💰 Còn {new_points:.1f} điểm ({int(new_points/QUESTION_COST)} câu)_"
            bot.reply_to(message, reply, parse_mode='Markdown')
        else:
            bot.reply_to(message, "Gemini không phản hồi. Thử hỏi lại bằng cách khác nhé!")
            
    except Exception as e:
        error_msg = str(e)
        print(f"Lỗi: {error_msg}")
        
        # Xử lý lỗi model cũ (404) bằng cách dùng model dự phòng (GIỐNG BẢN GỐC)
        if "404" in error_msg:
            bot.reply_to(message, "Hệ thống đang cập nhật model mới. Vui lòng đợi trong giây lát...")
            # Thử lại với model 2.0 ổn định
            try:
                fallback = genai.GenerativeModel('gemini-2.0-flash')
                res = fallback.generate_content(message.text)
                new_points = update_points(user_id, -QUESTION_COST)
                bot.reply_to(message, f"{res.text}\n\n_💰 Còn {new_points:.1f} điểm_", parse_mode='Markdown')
            except:
                bot.reply_to(message, "Không thể kết nối API. Kiểm tra lại API Key nhé!")
        else:
            bot.reply_to(message, "Có lỗi xảy ra, thử lại sau nhé!")

# ============ CALLBACK HANDLERS ============
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "link_guide":
        link_guide(call.message)

# ============ RUN BOT ============
if __name__ == "__main__":
    print("=" * 50)
    print(f"🤖 {BOT_NAME} Bot Starting...")
    print(f"📅 Birthday: {BOT_BIRTHDAY}")
    print(f"✅ Telegram: Connected")
    print(f"✅ Gemini AI: {MODEL_NAME}")
    print(f"✅ Firebase: {'Connected' if db else 'Offline Mode'}")
    print("=" * 50)
    
    bot.infinity_polling()
