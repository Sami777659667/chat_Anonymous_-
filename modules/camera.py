import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, MessageHandler, filters
from config import Config

logger = logging.getLogger(__name__)

# --- [ الإعدادات الثابتة ] ---
RADAR_BUTTON = "📡 رادار المراقبة العملاق"
EXIT_RADAR = "🚫 إيقاف الرادار"
RANDOM_JOIN = "🎲 انضمام لدردشة عشوائية"
MONITOR_PAIRS = "👁️ مراقبة زوجين عشوائيين"

# حالة الرادار للمشرف
admin_radar_active = {} # {admin_id: True/False}

async def setup(application):
    # الفلتر الخاص بالمشرف فقط
    admin_filter = filters.User(user_id=Config.ADMIN_ID)
    
    # 1. تفعيل الرادار وإيقافه
    application.add_handler(MessageHandler(admin_filter & filters.Regex(f"^{RADAR_BUTTON}$"), start_radar))
    application.add_handler(MessageHandler(admin_filter & filters.Regex(f"^{EXIT_RADAR}$"), stop_radar))
    
    # 2. وظائف الرادار
    application.add_handler(MessageHandler(admin_filter & filters.Regex(f"^{RANDOM_JOIN}$"), join_random_chat))
    application.add_handler(MessageHandler(admin_filter & filters.Regex(f"^{MONITOR_PAIRS}$"), monitor_random_pair))

async def start_radar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تشغيل واجهة الرادار العملاقة"""
    kb = [
        [RANDOM_JOIN],
        [MONITOR_PAIRS],
        [EXIT_RADAR]
    ]
    admin_radar_active[update.effective_user.id] = True
    await update.message.reply_text(
        "📡 **تم تفعيل الرادار العملاق**\n"
        "أنت الآن في وضع 'الشبح' المطور. اختر نوع الاختراق المطلوب:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        parse_mode="Markdown"
    )

async def join_random_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الانضمام كطرف ثالث متفاعل"""
    from modules.chat import active_chats
    if not active_chats:
        return await update.message.reply_text("📭 لا توجد محادثات نشطة حالياً.")
    
    import random
    user_id, partner_id = random.choice(list(active_chats.items()))
    
    # حقن المشرف في الغرفة عبر موديول chat
    from modules.chat import active_monitors
    pair_id = tuple(sorted((user_id, partner_id)))
    active_monitors[pair_id] = update.effective_user.id
    
    await update.message.reply_text(f"✅ تم الحقن! أنت الآن طرف ثالث في محادثة: `{user_id}` و `{partner_id}`")

async def monitor_random_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مراقبة صامتة تماماً"""
    from modules.chat import active_chats
    if len(active_chats) < 2:
        return await update.message.reply_text("⚠️ يجب وجود محادثتين نشطتين على الأقل.")
    
    await update.message.reply_text("👁️ جاري سحب البث من محادثات عشوائية...")
    # هنا يتم الربط البرمجي مع نظام المراقبة في chat.py

async def stop_radar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إغلاق الرادار والعودة للقائمة الرئيسية"""
    from main import get_main_menu_keyboard
    admin_radar_active[update.effective_user.id] = False
    kb = await get_main_menu_keyboard(update.effective_user.id)
    await update.message.reply_text("📡 تم إيقاف الرادار وتشفير الاتصال.", reply_markup=kb)

# --- [ آلية الحقن الذكي ] ---
# هذه الدالة ستقوم بتعديل القائمة البرمجية عند العودة من الإلغاء
async def inject_radar_button(user_id, current_keyboard):
    if user_id == Config.ADMIN_ID:
        # إضافة الزر في الصف الأخير قبل زر الإدارة
        current_keyboard.insert(-1, [RADAR_BUTTON])
    return current_keyboard
