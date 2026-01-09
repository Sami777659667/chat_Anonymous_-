import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler
from db import db
from config import Config

logger = logging.getLogger(__name__)

# --- [ الإعدادات الراقية ] ---
# ملاحظة: ملف main.py سيستخدم هذا المتغير لحقن الزر تلقائياً
MAIN_BUTTON = "🎁 المكافآت 🎁"
HOURLY_REWARD = 3
DAILY_REWARD = 15
HOUR_SECONDS = 3600
DAY_SECONDS = 8400

async def setup(application):
    # لمنع التكرار: نحذف أي نسخة من الزر مضافة بمفتاح يدوي سابق
    # ملف main.py سيقوم بإضافة الزر تلقائياً باستخدام مفتاح مسار الملف
    if "system_rewards_v2" in Config.DYNAMIC_BUTTONS:
        Config.DYNAMIC_BUTTONS.pop("system_rewards_v2")
    
    # ربط المعالجات فقط (الحقن يتم عبر main.py)
    application.add_handler(MessageHandler(filters.Regex(f"^{MAIN_BUTTON}$"), show_reward_vault), group=-1)
    application.add_handler(CallbackQueryHandler(handle_claims, pattern="^(claim_h|claim_d|refresh_m).*$"), group=-1)

def format_countdown(seconds):
    mins, secs = divmod(int(seconds), 60)
    hrs, mins = divmod(mins, 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"

async def show_reward_vault(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    now = time.time()
    
    wait_h = max(0, HOUR_SECONDS - (now - user_data.get("last_hourly", 0)))
    wait_d = max(0, DAY_SECONDS - (now - user_data.get("last_daily", 0)))

    text = (
        "✨ **مرحباً بك في مَنجم الهدايا المَلكي** ✨\n"
        "━━━━━━━━━━━━━━\n"
        f"💎 **هدايا الساعة:** `+{HOURLY_REWARD}` فلفل\n"
        f"◈ الحالة: {'🟢 متوفرة' if wait_h == 0 else f'⏳ `{format_countdown(wait_h)}`'}\n\n"
        f"👑 **المنحة اليومية:** `+{DAILY_REWARD}` فلفل\n"
        f"◈ الحالة: {'🟢 متوفرة' if wait_d == 0 else f'⏳ `{format_countdown(wait_d)}`'}\n"
        "━━━━━━━━━━━━━━\n"
        "💡 *استلام المنحة اليومية ينشط ظهورك في البحث العشوائي!*"
    )

    kb = [
        [InlineKeyboardButton("🎁 استلام هدية الساعة" if wait_h == 0 else f"⏳ {format_countdown(wait_h)}", callback_data="claim_h")],
        [InlineKeyboardButton("🌟 استلام المنحة الملكية" if wait_d == 0 else f"⏳ {format_countdown(wait_d)}", callback_data="claim_d")],
        [InlineKeyboardButton("🔄 تحديث", callback_data="refresh_m")]
    ]

    if update.callback_query:
        try: await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        except: pass
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def handle_claims(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = db.get_user(user_id)
    now = time.time()

    if query.data == "claim_h":
        if max(0, HOUR_SECONDS - (now - user_data.get("last_hourly", 0))) > 0:
            return await query.answer("⏳ لم يحن الوقت بعد", show_alert=True)
        db.update_points(user_id, HOURLY_REWARD)
        db.update_user_data(user_id, "last_hourly", now)
        await query.answer(f"✅ تم استلام {HOURLY_REWARD} فلفل!")
    elif query.data == "claim_d":
        if max(0, DAY_SECONDS - (now - user_data.get("last_daily", 0))) > 0:
            return await query.answer("👑 المنحة متاحة مرة كل 24 ساعة", show_alert=True)
        db.update_points(user_id, DAILY_REWARD)
        db.update_user_data(user_id, "last_daily", now)
        db.update_user_data(user_id, "join_date", now) # تنشيط البحث
        await query.answer(f"👑 تم استلام {DAILY_REWARD} فلفل وتنشيط حسابك!")
    
    await show_reward_vault(update, context)
