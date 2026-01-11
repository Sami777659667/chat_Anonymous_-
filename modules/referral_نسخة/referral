import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler
from db import db 

logger = logging.getLogger(__name__)

# تأكد أن هذا النص يطابق الزر في main.py تماماً
MAIN_BUTTON = "💎برنامج الإحالات💎"
REWARD_AMOUNT = 70 

async def setup(application):
    # استخدام group=-1 لضمان استجابة الزر قبل فلاتر الدردشة
    application.add_handler(MessageHandler(filters.Regex(f"^{MAIN_BUTTON}$"), show_referral_menu), group=-1)
    application.add_handler(CallbackQueryHandler(show_top_referrals, pattern="^top_refs$"), group=-1)
    application.add_handler(CallbackQueryHandler(show_referral_menu, pattern="^refresh_ref$"), group=-1)

async def show_referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    # جلب البيانات من MongoDB
    user_data = db.get_user(user_id)
    invited_count = user_data.get("referred_count", 0)

    text = (
        f"🔥 **نظام الأرباح الملكي (70 🌶️ لكل صديق!)** 🔥\n"
        f"━━━━━━━━━━━━━━\n"
        f"انشر رابطك واحصل على ثروة من الفلفل فوراً!\n\n"
        f"🔗 رابطك الخاص:\n`{ref_link}`\n\n"
        f"👥 أصدقاء دعوتهم: `{invited_count}`\n"
        f"💰 إجمالي أرباحك: `{invited_count * REWARD_AMOUNT}` 🌶️\n\n"
        f"📢 **ملاحظة:** الغش يؤدي لحظر الحساب نهائياً."
    )
    
    kb = [
        [InlineKeyboardButton("🏆 ملوك الإحالة (جوائز VIP)", callback_data="top_refs")],
        [InlineKeyboardButton("📤 مشاركة الرابط", url=f"https://t.me/share/url?url={ref_link}&text=انضم%20لأقوى%20بوت%20دردشة%20واحصل%20على%20هدايا!")]
    ]
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_top_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # جلب أعلى 10 أشخاص من MongoDB
    top_refs = list(db.db.users.find({"referred_count": {"$gt": 0}}).sort("referred_count", -1).limit(10))
    
    text = "🏆 **قائمة ملوك الإحالة** 🏆\n"
    text += "━━━━━━━━━━━━━━\n"
    text += "🎁 **مفاجأة:** المتصدرون في هذه القائمة سيحصلون على اشتراك **VIP مجاني** شهرياً!\n\n"
    
    if not top_refs:
        text += "📭 لا توجد إحالات حالياً، كن الأول!"
    else:
        medals = ["🥇", "🥈", "🥉", "👤", "👤", "👤", "👤", "👤", "👤", "👤"]
        for i, user in enumerate(top_refs):
            nick = user.get("nickname", "عضو متميز")
            count = user.get("referred_count", 0)
            text += f"{medals[i]} `{count: <3} إحالة` ⇽ **{nick}**\n"
            
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="refresh_ref")]]), parse_mode="Markdown")
