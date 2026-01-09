import logging
import asyncio
import time
import os
import sys
import random
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

# --- [ حل مشكلة المسارات للاستيراد ] ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from db import db
    from config import Config
    # استيراد بيانات الشات للمراقبة
    from modules.chat import active_chats, waiting_queue
except ImportError as e:
    logging.error(f"❌ Error importing modules: {e}")
    # قيم افتراضية لتجنب الانهيار في حال فشل الاستيراد
    active_chats = {}
    waiting_queue = []

logger = logging.getLogger(__name__)

# الأزرار الرئيسية
ADMIN_BUTTON = "🛠️ لوحة المشرف"
SPY_BUTTON = "👁️ بحث للمراقبة (عين الصقر)"

async def setup(application):
    # استخدام المجموعة -1 لضمان الأولوية القصوى للآدمن
    application.add_handler(MessageHandler(filters.Regex(f"^{ADMIN_BUTTON}$"), admin_menu), group=-1)
    application.add_handler(MessageHandler(filters.Regex(f"^{SPY_BUTTON}$"), spy_on_chat), group=-1)
    
    # أوامر التحكم (Commands)
    application.add_handler(CommandHandler("ban", ban_user), group=-1)
    application.add_handler(CommandHandler("unban", unban_user), group=-1)
    application.add_handler(CommandHandler("give", give_pepper), group=-1)
    application.add_handler(CommandHandler("give_all", give_all_pepper), group=-1)
    application.add_handler(CommandHandler("vip", give_vip), group=-1)
    application.add_handler(CommandHandler("send", send_to_user), group=-1)
    application.add_handler(CommandHandler("broadcast", broadcast_all), group=-1)

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != Config.ADMIN_ID: return
    
    kb = [[SPY_BUTTON], ["🏠 القائمة الرئيسية"]]
    
    admin_text = (
        "😎 **أهلاً بك يا زعيم في لوحة التحكم المطلقة:**\n"
        "━━━━━━━━━━━━━━\n"
        "• `/ban ID` : حظر مستخدم\n"
        "• `/unban ID` : فك الحظر\n"
        "• `/give ID QNT` : منح فلفل لمستخدم\n"
        "• `/give_all QNT` : منح فلفل للكل 🌶️\n"
        "• `/vip ID DAYS` : منح VIP (أيام)\n"
        "• `/send ID text` : رسالة خاصة لمستخدم\n"
        "• `/broadcast text` : إذاعة شاملة\n"
        "━━━━━━━━━━━━━━\n"
        "👁️ **وضع المراقبة:** يتيح لك رؤية المحادثات القائمة."
    )
    await update.message.reply_text(admin_text, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode="Markdown")

# --- [ نظام المراقبة (عين الصقر) ] ---
async def spy_on_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != Config.ADMIN_ID: return
    
    stats_text = (
        f"📊 **حالة النظام الآن:**\n"
        f"👥 في الانتظار: `{len(waiting_queue)}` مستخدم\n"
        f"💬 محادثات نشطة: `{len(active_chats) // 2}` محادثة\n\n"
    )

    if not active_chats:
        return await update.message.reply_text(stats_text + "📭 لا توجد محادثات نشطة حالياً للمراقبة.")

    # اختيار عينة من المحادثات النشطة
    u_ids = list(active_chats.keys())
    user_a = random.choice(u_ids)
    user_b = active_chats[user_a]

    # جلب بيانات الشريكين
    data_a = db.get_user(user_a)
    data_b = db.get_user(user_b)

    spy_report = (
        f"{stats_text}"
        f"👁️ **تفاصيل المحادثة المختارة:**\n"
        f"👤 الطرف الأول: `{user_a}` ({data_a.get('nickname', 'مجهول')})\n"
        f"👤 الطرف الثاني: `{user_b}` ({data_b.get('nickname', 'مجهول')})\n"
        f"━━━━━━━━━━━━━━\n"
        f"استخدم `/send` لإرسال تحذير أو تدخل إداري."
    )
    await update.message.reply_text(spy_report, parse_mode="Markdown")

# --- [ أوامر التحكم المباشر ] ---

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != Config.ADMIN_ID or not context.args: return
    target_id = int(context.args[0])
    db.update_user_data(target_id, "is_banned", True)
    await update.message.reply_text(f"🚫 تم حظر المستخدم `{target_id}` نهائياً.")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != Config.ADMIN_ID or not context.args: return
    target_id = int(context.args[0])
    db.update_user_data(target_id, "is_banned", False)
    await update.message.reply_text(f"✅ تم فك الحظر عن `{target_id}`.")

async def give_pepper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != Config.ADMIN_ID or len(context.args) < 2: return
    target_id, amount = int(context.args[0]), int(context.args[1])
    db.update_points(target_id, amount)
    await update.message.reply_text(f"🌶️ تم منح `{amount}` فلفل للمستخدم `{target_id}`.")

async def give_all_pepper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != Config.ADMIN_ID or not context.args: return
    amount = int(context.args[0])
    db.db.users.update_many({}, {"$inc": {"points": amount}})
    await update.message.reply_text(f"🎊 كرم ملكي! تم منح `{amount}` فلفل لجميع المستخدمين.")

async def give_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != Config.ADMIN_ID or len(context.args) < 2: return
    target_id, days = int(context.args[0]), int(context.args[1])
    expiry = time.time() + (days * 86400)
    db.db.users.update_one({"user_id": target_id}, {"$set": {"is_vip": True, "vip_expiry": expiry}})
    await update.message.reply_text(f"👑 تم منح VIP للمستخدم `{target_id}` لمدة `{days}` أيام.")

async def send_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != Config.ADMIN_ID or len(context.args) < 2: return
    target_id = int(context.args[0])
    msg = " ".join(context.args[1:])
    try:
        await context.bot.send_message(target_id, f"✉️ **رسالة رسمية من الإدارة:**\n\n{msg}", parse_mode="Markdown")
        await update.message.reply_text("✅ تم إرسال الرسالة.")
    except:
        await update.message.reply_text("❌ فشل الإرسال.")

async def broadcast_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != Config.ADMIN_ID or not context.args: return
    msg = " ".join(context.args)
    users = db.db.users.find({}, {"user_id": 1})
    count = 0
    for user in users:
        try:
            await context.bot.send_message(user["user_id"], f"📢 **إعلان ملكي:**\n\n{msg}", parse_mode="Markdown")
            count += 1
            await asyncio.sleep(0.05)
        except: continue
    await update.message.reply_text(f"✅ تم الإذاعة لـ {count} مستخدم.")
