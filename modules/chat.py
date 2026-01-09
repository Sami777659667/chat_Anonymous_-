import logging
import asyncio
import re
import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CommandHandler

# --- [ حل مشكلة المسارات لضمان العمل على GitHub ] ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from db import db
    from config import Config
    # استيراد وظيفة بدء اللعبة من ملف الألعاب
    from modules.game import start_xo_from_chat
except ImportError:
    logging.error("❌ فشل استيراد الملحقات الأساسية في ملف الدردشة")

logger = logging.getLogger(__name__)

# --- [ الإعدادات والأزرار الملكية ] ---
MAIN_BUTTON = "🚀 البحث عن شريك عشوائي"
EXIT_SEARCH = "إلغاء البحث ❌"
STOP_CHAT = "🛑 إنهاء المحادثة"
PLAY_XO = "🎮 العب XO مع الشريك"

waiting_queue = []
active_chats = {} # {user_id: partner_id}

async def setup(application):
    # تسجيل الزر الرئيسي في القائمة الديناميكية
    Config.DYNAMIC_BUTTONS[__name__] = MAIN_BUTTON

    # معالجة أزرار التحكم (إيقاف البحث والدردشة) بمجموعة أولوية -1
    application.add_handler(MessageHandler(filters.Regex(f"^({EXIT_SEARCH}|{STOP_CHAT})$"), stop_command), group=-1)
    
    # بدء البحث
    application.add_handler(MessageHandler(filters.Regex(f"^{MAIN_BUTTON}$"), start_search), group=0)
    
    # زر اللعب داخل الدردشة
    application.add_handler(MessageHandler(filters.Regex(f"^{PLAY_XO}$"), invite_to_game), group=1)
    
    # محرك نقل الرسائل والفلترة
    chat_filters = filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({EXIT_SEARCH}|{MAIN_BUTTON}|{STOP_CHAT}|{PLAY_XO}|🏠|🕹️)")
    application.add_handler(MessageHandler(chat_filters, forward_message), group=1)

# --- [ وظائف الحماية والفلترة الذكية ] ---
def has_invite_permission(user_id):
    user = db.get_user(user_id)
    # فك الحظر إذا دعا شخص واحد أو كان VIP
    if user.get("referred_count", 0) >= 1 or user.get("is_vip"):
        return True
    return False

def contains_ads(text):
    # فحص الروابط أو المعرفات @ لضمان عدم الترويج
    pattern = r"(http://|https://|t\.me/|@[\w_]+)"
    return re.search(pattern, text, re.IGNORECASE)

# --- [ محرك البحث والمطابقة ] ---
async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in active_chats:
        await update.message.reply_text("⚠️ أنت في محادثة نشطة بالفعل!")
        return

    if user_id not in waiting_queue:
        waiting_queue.append(user_id)
        kb = [[EXIT_SEARCH]]
        await update.message.reply_text(
            "🔎 **جاري البحث عن شريك لائق بك...**\n"
            "سيتم توصيلك تلقائياً فور توفر مستخدم متاح.",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
            parse_mode="Markdown"
        )
    
    # محاولة مطابقة مستخدمين
    if len(waiting_queue) >= 2:
        u1 = waiting_queue.pop(0)
        u2 = waiting_queue.pop(0)
        
        active_chats[u1] = u2
        active_chats[u2] = u1
        
        await notify_match(context, u1, u2)

async def notify_match(context, u1, u2):
    d1 = db.get_user(u1)
    d2 = db.get_user(u2)
    
    # أزرار التحكم أثناء الدردشة (إضافة زر XO)
    kb = [[STOP_CHAT], [PLAY_XO]]
    markup = ReplyKeyboardMarkup(kb, resize_keyboard=True)

    def format_info(data):
        vip_tag = "👑 [VIP]" if data.get("is_vip") else "👤 [عضو]"
        return (
            f"👤 **اللقب:** {data.get('nickname', 'نخبة ✨')}\n"
            f"🎭 **الحالة:** {vip_tag}\n"
            f"🌍 **الدولة:** {data.get('country', 'غير محدد')}\n"
            f"🎂 **العمر:** {data.get('age', 'غير محدد')}\n"
            f"🌶️ **النقاط:** {data.get('points', 0)}"
        )

    msg_head = "✨ **تم العثور على شريك متصل!**\n\n"
    
    await context.bot.send_message(u1, msg_head + format_info(d2) + "\n\nاستمتعوا بالدردشة واللعب بذكاء!", reply_markup=markup, parse_mode="Markdown")
    await context.bot.send_message(u2, msg_head + format_info(d1) + "\n\nاستمتعوا بالدردشة واللعب بذكاء!", reply_markup=markup, parse_mode="Markdown")

# --- [ محرك نقل الرسائل والفلترة ] ---
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    partner_id = active_chats.get(user_id)
    text = update.message.text

    if not partner_id: return

    # نظام فلترة الروابط واليوزرات
    if contains_ads(text):
        if not has_invite_permission(user_id):
            await update.message.reply_text(
                "🚫 **نظام الحماية:** لا يمكنك إرسال روابط أو معرفات حتى تقوم بدعوة صديق واحد على الأقل للبوت."
            )
            return

    try:
        user_data = db.get_user(user_id)
        nick = user_data.get("nickname", "مجهول")
        await context.bot.send_message(partner_id, f"💬 **{nick}**: {text}", parse_mode="Markdown")
    except Exception:
        await stop_command(update, context)

# --- [ زر استدعاء لعبة XO ] ---
async def invite_to_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    partner_id = active_chats.get(user_id)
    
    if not partner_id:
        await update.message.reply_text("⚠️ يجب أن تكون في محادثة لتلعب مع شريكك.")
        return

    try:
        # إرسال إشعار للطرفين ببدء اللعبة
        await update.message.reply_text("🎲 جاري بدء تحدي XO مع شريكك...")
        await context.bot.send_message(partner_id, "🎮 شريكك دعاك لتحدي XO الآن!")
        
        # استدعاء الوظيفة من ملف game.py مباشرة
        await start_xo_from_chat(context, user_id, partner_id)
    except Exception as e:
        logger.error(f"Error starting game from chat: {e}")
        await update.message.reply_text("❌ نظام الألعاب غير متصل حالياً.")

# --- [ إنهاء الدردشة ] ---
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # إزالة من الانتظار إذا كان يبحث
    if user_id in waiting_queue:
        waiting_queue.remove(user_id)
    
    partner_id = active_chats.pop(user_id, None)
    
    from main import get_main_menu_keyboard
    main_kb = await get_main_menu_keyboard(user_id)

    if partner_id:
        active_chats.pop(partner_id, None)
        await context.bot.send_message(partner_id, "🛑 تم إنهاء المحادثة من قبل الشريك.", reply_markup=await get_main_menu_keyboard(partner_id))
        await update.message.reply_text("✅ تم إغلاق المحادثة بنجاح.", reply_markup=main_kb)
    else:
        await update.message.reply_text("🏠 تم العودة للقائمة الرئيسية.", reply_markup=main_kb)
