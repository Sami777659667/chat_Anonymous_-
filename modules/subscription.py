import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler, TypeHandler

logger = logging.getLogger(__name__)

# --- [ الإعدادات الصارمة ] ---
CHANNEL_ID = "@NN26S"
GROUP_ID = -1003493496120 
CHANNEL_LINK = "https://t.me/NN26S"
GROUP_LINK = "https://t.me/Anonymousa_Arabic"

# نص الزر الأساسي الذي سيظهر في الكيبورد بالأسفل
VERIFY_BUTTON_TEXT = "🛡️ فحص حالة الاشتراك وتفعيل البوت"

async def setup(application):
    # المجموعة -100 لضمان التنفيذ قبل أي موديول آخر نهائياً
    application.add_handler(TypeHandler(Update, mandatory_guard), group=-100)
    # معالج الضغط على زر الكيبورد الثابت
    application.add_handler(MessageHandler(filters.Regex(f"^{VERIFY_BUTTON_TEXT}$"), handle_verify_request), group=-100)

async def is_subscribed(bot, user_id):
    """تحقق فني صارم"""
    try:
        ch = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        gr = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        allowed = ['member', 'administrator', 'creator']
        return ch.status in allowed and gr.status in allowed
    except:
        return False

async def mandatory_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منع ظهور أي شيء ما لم يشترك"""
    if not update.effective_chat or update.effective_chat.type != "private":
        return

    user_id = update.effective_user.id
    
    # استثناء زر التحقق نفسه من المنع
    if update.message and update.message.text == VERIFY_BUTTON_TEXT:
        return

    if not await is_subscribed(context.bot, user_id):
        # إنشاء كيبورد أسفل الشاشة يحتوي على زر واحد فقط (إجباري)
        fixed_kb = ReplyKeyboardMarkup([[KeyboardButton(VERIFY_BUTTON_TEXT)]], resize_keyboard=True)
        
        # أزرار الروابط (للتوجيه)
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 انضم للقناة الرسمية", url=CHANNEL_LINK)],
            [InlineKeyboardButton("💬 انضم لمجموعة الدردشة", url=GROUP_LINK)]
        ])

        text = (
            "⚠️ **تـنبيه أمني: الـوصول مـحجوب!**\n"
            "━━━━━━━━━━━━━━\n"
            "عذراً يا عزيزي، نظام الحماية يمنع استخدام البوت قبل الانضمام لقنواتنا الرسمية.\n\n"
            "✅ **خطوات التفعيل:**\n"
            "1️⃣ اشترك في القناة والمجموعة بالأسفل.\n"
            "2️⃣ اضغط على الزر الكبير بالأسفل (فحص الحالة).\n\n"
            "🛡️ *سيتم فتح كافة المميزات تلقائياً بعد الاشتراك.*"
        )
        
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=fixed_kb, # زر ثابت بالأسفل
            parse_mode="Markdown"
        )
        
        # إرسال أزرار الروابط كرسالة ثانية للتوضيح
        await context.bot.send_message(
            chat_id=user_id,
            text="🔗 **روابط الانضمام السريعة:**",
            reply_markup=inline_kb,
            parse_mode="Markdown"
        )
        
        raise context.ApplicationHandlerStop

async def handle_verify_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة طلب التحقق من زر الكيبورد الثابت"""
    user_id = update.effective_user.id
    
    if await is_subscribed(context.bot, user_id):
        # إذا اشترك، نرسل له رسالة نجاح ونستدعي الـ Start لإظهار المنيو الحقيقي
        await update.message.reply_text("✅ **عبقري! تم التحقق بنجاح.**\nجاري تشغيل محرك البوت...", parse_mode="Markdown")
        from main import start
        await start(update, context)
    else:
        # إذا لم يشترك، نبقي القفل كما هو مع تنبيه
        await update.message.reply_text(
            "❌ **لم يتم العثور على اشتراكك بعد!**\n"
            "يرجى التأكد من الانضمام للقناة والمجموعة ثم المحاولة مرة أخرى.",
            parse_mode="Markdown"
        )
