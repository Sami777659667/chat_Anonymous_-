import logging
import time
import os
import sys
import random
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters

# --- [ نظام المسارات العالمي لضمان العمل في كل البيئات ] ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from db import db
    from config import Config
except ImportError:
    import db
    from config import Config

logger = logging.getLogger(__name__)

# --- [ الإعدادات الملكية ] ---
MAIN_BUTTON = "🪪 البيانات الشخصية 🪪"
EDIT_DATA_BTN = "⚙️ تعديل هويتي الملكية"
STATS_BTN = "📊 احصائيات"
BALANCE_BTN = "💳 رصيدي"
BACK_BUTTON = "🏠 القائمة الرئيسية"
CANCEL_BTN = "إلغاء ❌"

# الأسعار بالفلفل
PRICES = {"nickname": 25, "gender": 30, "country": 20, "age": 15}

async def setup(application):
    # [قوة الحقن]: تسجيل الزر في الإعدادات المركزية ليراه ملف main.py
    Config.DYNAMIC_BUTTONS[__name__] = MAIN_BUTTON

    # معالجات الأولوية القصوى (Group -1) لضمان الاستجابة الفورية للأزرار
    application.add_handler(MessageHandler(filters.Regex(f"^{MAIN_BUTTON}$"), show_profile_hub), group=-1)
    application.add_handler(MessageHandler(filters.Regex(f"^{EDIT_DATA_BTN}$"), show_edit_menu), group=-1)
    application.add_handler(MessageHandler(filters.Regex(f"^{CANCEL_BTN}$"), cancel_edit), group=-1)
    application.add_handler(MessageHandler(filters.Regex(f"^{BACK_BUTTON}$"), back_to_main), group=-1)
    
    # معالجة بقية الأزرار
    application.add_handler(MessageHandler(filters.Regex(f"^{STATS_BTN}$"), show_bot_stats))
    application.add_handler(MessageHandler(filters.Regex(f"^{BALANCE_BTN}$"), show_balance))
    
    # التقاط أزرار الحقول (اللقب، الجنس، إلخ)
    field_filter = filters.Regex(r"^(🏷️ لقبك|👤 جنسك|🌍 موطنك|🎂 عمرك)")
    application.add_handler(MessageHandler(field_filter, start_edit_flow))
    
    # معالج إدخال البيانات (يتم تفعيله فقط أثناء التعديل)
    # نستخدم Group 2 لضمان عدم تداخله مع نظام الدردشة أو الأزرار
    input_filter = (filters.TEXT & ~filters.COMMAND & 
                   ~filters.Regex(f"^({MAIN_BUTTON}|{EDIT_DATA_BTN}|{BACK_BUTTON}|{STATS_BTN}|{BALANCE_BTN}|{CANCEL_BTN}|🏷️|👤|🌍|🎂)$"))
    application.add_handler(MessageHandler(input_filter, save_data_to_mongo), group=2)

# --- [ الوظائف البرمجية ] ---

async def show_profile_hub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = db.get_user(user_id)
    
    kb = [[EDIT_DATA_BTN], [STATS_BTN, BALANCE_BTN], [BACK_BUTTON]]
    
    text = (
        f"🏆 **ملفك الشخصي الملكي**\n"
        f"━━━━━━━━━━━━━━\n"
        f"⚜️ **اللقب:** {u.get('nickname', 'نخبة ✨')}\n"
        f"📍 **الموطن:** {u.get('country', 'غير محدد')}\n"
        f"🕯 **العمر:** {u.get('age', 'غير محدد')}\n"
        f"🧬 **الجنس:** {u.get('gender', 'غير محدد')}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🌶️ **الرصيد:** {u.get('points', 0)} فلفل\n"
        f"👑 **الحالة:** {'عضو VIP ✅' if u.get('is_vip') else 'عضو عادي'}\n"
        f"━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode="Markdown")

async def show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["🏷️ لقبك", "👤 جنسك"], ["🌍 موطنك", "🎂 عمرك"], [BACK_BUTTON]]
    await update.message.reply_text(
        "⚙️ **قسم التعديل الملكي**\n\n"
        "ملاحظة: التعديل الأول مجاني تماماً، التعديلات اللاحقة تكلف رصيد فلفل.",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def start_edit_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    field_map = {"🏷️ لقبك": "nickname", "👤 جنسك": "gender", "🌍 موطنك": "country", "🎂 عمرك": "age"}
    field = field_map.get(text)
    
    user_id = update.effective_user.id
    u = db.get_user(user_id)
    
    # فحص المجانية (إذا كانت القيمة لسه افتراضية)
    current_val = u.get(field, "")
    is_free = current_val in ["نخبة ✨", "غير محدد", "", "مجهول"]
    
    context.user_data['editing_field'] = field
    context.user_data['is_free'] = is_free
    
    kb = [[CANCEL_BTN]]
    if field == "gender": kb = [["ذكر ♂️", "أنثى ♀️"], [CANCEL_BTN]]
    
    msg = "🎁 **تعديل مجاني لأول مرة!**" if is_free else f"💳 التكلفة: **{PRICES[field]} فلفل**"
    await update.message.reply_text(f"✍️ أرسل **{text}** الجديد الآن:\n{msg}", 
                                   reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode="Markdown")

async def save_data_to_mongo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data.get('editing_field')
    if not field: return # إذا لم يكن في حالة تعديل لا يفعل شيئاً

    user_id = update.effective_user.id
    new_val = update.message.text
    is_free = context.user_data.get('is_free', False)

    if not is_free:
        points = db.get_points(user_id)
        if points < PRICES[field]:
            await update.message.reply_text("❌ رصيدك لا يكفي لإتمام هذا التعديل!")
            context.user_data.clear()
            return
        db.update_points(user_id, -PRICES[field])

    db.update_user_data(user_id, field, new_val)
    context.user_data.clear()
    
    await update.message.reply_text(f"✅ تم تحديث بياناتك بنجاح إلى: **{new_val}**")
    await show_profile_hub(update, context)

async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("📥 تم إلغاء عملية التعديل.")
    await show_profile_hub(update, context)

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from main import get_main_menu_keyboard
    kb = await get_main_menu_keyboard(update.effective_user.id)
    await update.message.reply_text("🏠 عدت للقائمة الرئيسية.", reply_markup=kb)

async def show_bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = db.db.users.count_documents({})
    await update.message.reply_text(f"📊 **إحصائيات المملكة:**\n\n👥 عدد المواطنين: {total}\n🌐 الحالة: متصل ✅", parse_mode="Markdown")

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = db.get_user(update.effective_user.id)
    await update.message.reply_text(f"💳 **رصيدك الحالي:**\n\n🌶️ فلفل: {u.get('points', 0)}\n⭐ نجوم: {u.get('stars', 0)}", parse_mode="Markdown")
