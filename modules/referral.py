import logging
import asyncio
import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler

# --- [ إعدادات المسارات ] ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from db import db
    from config import Config
except:
    logging.error("❌ فشل استيراد الملحقات الأساسية")

# --- [ الثوابت الملكية ] ---
MAIN_BUTTON = "🌟 كسب النجوم 🌟"
SUB_BTN_EARN = "💎 ربح النجوم"
SUB_BTN_WITHDRAW = "💳 سحب النجوم"
SUB_BTN_EXCHANGE = "🔄 صرف الفلفل"
BACK_BTN = "🔙 العودة للقائمة"

MIN_WITHDRAW = 500
MAX_WITHDRAW = 20000
EXCHANGE_RATE = 40 
MIN_EXCHANGE = 400

async def setup(application):
    Config.DYNAMIC_BUTTONS[__name__] = MAIN_BUTTON
    
    # معالجات الأزرار النصية (أولوية قصوى -1)
    application.add_handler(MessageHandler(filters.Regex(f"^{MAIN_BUTTON}$"), show_referral_hub), group=-1)
    application.add_handler(MessageHandler(filters.Regex(f"^{SUB_BTN_EARN}$"), earn_stars_info), group=-1)
    application.add_handler(MessageHandler(filters.Regex(f"^{SUB_BTN_WITHDRAW}$"), start_withdrawal), group=-1)
    application.add_handler(MessageHandler(filters.Regex(f"^{SUB_BTN_EXCHANGE}$"), start_exchange), group=-1)
    application.add_handler(MessageHandler(filters.Regex(f"^{BACK_BTN}$"), back_to_main), group=-1)
    
    # الكولباك لمعالجة الأزرار المضمنة
    application.add_handler(CallbackQueryHandler(handle_actions, pattern="^(meth_|confirm_|cancel_)"))

    # معالج المدخلات النصية (الأولوية الأخيرة group=10 لمنع التضارب)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic_inputs), group=10)

# --- [ الواجهات ] ---

async def show_referral_hub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear() # مسح أي حالة قديمة عند فتح القائمة
    kb = [[SUB_BTN_EARN, SUB_BTN_WITHDRAW], [SUB_BTN_EXCHANGE, BACK_BTN]]
    await update.message.reply_text(
        "✨ **مرحباً بك في بنك النجوم الملكي** ✨\n\nإدارة أرباحك، سحب النجوم، أو تحويل الفلفل لثروة!",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    from main import get_main_menu_keyboard
    await update.message.reply_text("🏠 العودة للقائمة الرئيسية...", reply_markup=await get_main_menu_keyboard(update.effective_user.id))

# --- [ قسم ربح النجوم ] ---

async def earn_stars_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{u.id}"
    
    text = (
        f"💎 **برنامج الإحالات الملكي** 💎\n\n"
        f"🔥 نظام الأرباح: (70 🌶️ لكل صديق!) 🔥\n"
        f"🌟 مكافأة إضافية: **10 نجوم** ⭐ لكل صديق\n"
        f"━━━━━━━━━━━━━━\n"
        f"🔗 **رابطك الخاص:**\n`{ref_link}`"
    )
    kb = [[InlineKeyboardButton("🎁 توزيع 10 نجوم ⭐", url=f"https://t.me/share/url?url={ref_link}&text=أتحداك تدخل وتربح 10 نجوم مجاناً! 🎁")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# --- [ منطق السحب (الأزرار) ] ---

async def start_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = [
        [InlineKeyboardButton("👤 تلجرام", callback_data="meth_Telegram"), InlineKeyboardButton("💳 بطاقة بنكية", callback_data="meth_Bank")],
        [InlineKeyboardButton("🅿️ PayPal", callback_data="meth_PayPal"), InlineKeyboardButton("🅿️ Payeer", callback_data="meth_Payeer")]
    ]
    await update.message.reply_text("💳 **سحب النجوم ⭐**\n\nيرجى اختيار طريقة السحب من الأسفل 👇", reply_markup=InlineKeyboardMarkup(kb))

async def handle_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data.startswith("meth_"):
        meth = data.split("_")[1]
        context.user_data['w_meth'] = meth
        context.user_data['w_step'] = 'WAIT_NUM' # تفعيل حالة انتظار الرقم
        await query.message.edit_text(
            f"✅ اخترت السحب عبر: **{meth}**\n\n"
            f"• الحد الأدنى: {MIN_WITHDRAW} ⭐\n"
            "📥 **أرسل الآن عدد النجوم الذي تريد سحبه (أرقام فقط):**"
        )
    
    elif data == "confirm_final":
        await query.message.edit_text("⏳ **جاري معالجة طلبك...**\nسنتحقق من البيانات ونرسل لك إشعاراً قريباً.")
        await asyncio.sleep(2)
        await query.message.reply_text("❌ **عذراً، فشلت العملية!**\nيرجى إعادة المحاولة لاحقاً بسبب ضغط الطلبات.")
        context.user_data.clear()
        
    elif data == "cancel_withdraw":
        await query.message.edit_text("❌ تم إلغاء طلب السحب.")
        context.user_data.clear()

# --- [ منطق الصرف (البداية) ] ---

async def start_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user_p = db.get_user(update.effective_user.id).get("points", 0)
    await update.message.reply_text(
        f"🔄 **محول الفلفل الملكي**\n\n"
        f"سعر الصرف: **40 فلفل = 1 نجمة ⭐**\n"
        f"رصيدك: `{user_p}` 🌶️\n\n"
        f"📥 **أرسل كمية الفلفل المراد تحويلها (أدنى حد {MIN_EXCHANGE}):**"
    )
    context.user_data['w_step'] = 'WAIT_EX_NUM'

# --- [ المعالج الذكي للمدخلات - قلب النظام ] ---

async def handle_logic_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # إذا لم تكن هناك حالة نشطة، اخرج فوراً للسماح للأولويات الأخرى بالعمل
    if 'w_step' not in context.user_data:
        return

    user_id = update.effective_user.id
    step = context.user_data.get('w_step')
    text = update.message.text

    # الحالة 1: انتظار رقم النجوم للسحب
    if step == 'WAIT_NUM':
        if not text.isdigit():
            return await update.message.reply_text("⚠️ **القيمة ليست رقماً.**\nℹ️ أدخل أرقاماً بين 500 و 20000...")
        
        num = int(text)
        if num < MIN_WITHDRAW or num > MAX_WITHDRAW:
            return await update.message.reply_text(f"❌ **خارج النطاق!**\nأدخل قيمة بين {MIN_WITHDRAW} و {MAX_WITHDRAW}.")
        
        # فحص رصيد النجوم (بافتراض وجود حقل stars في DB)
        user_stars = db.get_user(user_id).get("stars", 0)
        if num > user_stars:
            bot_username = (await context.bot.get_me()).username
            ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
            return await update.message.reply_text(
                f"❌ **رصيدك لا يكفي!**\nرصيدك الحالي: {user_stars} ⭐\n\nاكسب المزيد عبر رابطك:\n{ref_link}"
            )

        context.user_data['w_amt'] = num
        context.user_data['w_step'] = 'WAIT_INFO'
        await update.message.reply_text("✅ ممتاز. الآن يرجى إرسال **معلومات السحب** (الاسم والحساب) في رسالة واحدة:")

    # الحالة 2: انتظار معلومات الحساب
    elif step == 'WAIT_INFO':
        amt = context.user_data.get('w_amt')
        meth = context.user_data.get('w_meth')
        kb = [[InlineKeyboardButton("✅ تأكيد", callback_data="confirm_final"), InlineKeyboardButton("❌ إلغاء", callback_data="cancel_withdraw")]]
        await update.message.reply_text(
            f"❓ **تأكيد السحب:**\n\n"
            f"• سحب: `{amt}` ⭐\n"
            f"• الطريقة: `{meth}`\n"
            f"• المعلومات: `{text}`\n\n"
            "هل أنت متأكد؟",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        context.user_data['w_step'] = None # إنهاء تتابع الحالات

    # الحالة 3: انتظار كمية الفلفل للصرف
    elif step == 'WAIT_EX_NUM':
        if not text.isdigit():
            return await update.message.reply_text("ℹ️ أدخل قيمة رقمية للصرف...")
        
        amt = int(text)
        if amt < MIN_EXCHANGE:
            return await update.message.reply_text(f"⚠️ أدنى حد للتحويل هو {MIN_EXCHANGE} 🌶️.")
        
        user_p = db.get_user(user_id).get("points", 0)
        if amt > user_p:
            return await update.message.reply_text("❌ رصيد فلفلك غير كافٍ للصرف!")

        stars_gained = amt // EXCHANGE_RATE
        db.update_points(user_id, -amt)
        # تحديث النجوم في القاعدة
        db.db.users.update_one({"user_id": user_id}, {"$inc": {"stars": stars_gained}})
        
        await update.message.reply_text(
            f"✅ **تم التحويل بنجاح!**\n\n"
            f"♨️ خصم: `{amt}` 🌶️\n"
            f"✨ إضافة: `{stars_gained}` ⭐\n"
            f"💰 رصيدك الآن: `{db.get_user(user_id).get('stars', 0)}` ⭐"
        )
        context.user_data.clear()
