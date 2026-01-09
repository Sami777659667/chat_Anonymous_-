import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from db import db 

logger = logging.getLogger(__name__)

MAIN_BUTTON = "🏆 المتصدرون 🏆"

async def setup(application):
    # استخدام group=-1 لضمان الأولوية القصوى
    application.add_handler(MessageHandler(filters.Regex(f"^{MAIN_BUTTON}$"), show_leaderboard), group=-1)

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # التعديل هنا: المقارنة الصريحة بـ None لتجنب NotImplementedError
    if db.db is None:
        return await update.message.reply_text("❌ خطأ: لم يتم الاتصال بقاعدة البيانات.")

    try:
        # جلب أعلى 10 مستخدمين
        top_users = list(db.db.users.find().sort("points", -1).limit(10))
        
        if not top_users:
            return await update.message.reply_text("📭 القائمة فارغة حالياً!")

        leader_text = "🏆 **قائمة عمالقة الفلفل (أعلى 10)** 🏆\n"
        leader_text += "━━━━━━━━━━━━━━\n\n"
        
        medals = ["🥇", "🥈", "🥉", "👤", "👤", "👤", "👤", "👤", "👤", "👤"]
        
        for i, user in enumerate(top_users):
            nickname = user.get('nickname', 'عضو جديد ✨')
            points = user.get('points', 0)
            prefix = "⭐ " if user.get('user_id') == user_id else medals[i]
            leader_text += f"{prefix} `{points: <5}` ⇽ **{nickname}**\n"
        
        leader_text += "\n━━━━━━━━━━━━━━\n"
        await update.message.reply_text(leader_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"❌ Leaderboard Error: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء تحديث القائمة.")
