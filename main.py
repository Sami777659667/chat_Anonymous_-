import os
import importlib
import logging
import asyncio
import sys
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from config import Config
from db import db

# إعداد السجلات
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- [ نظام بناء القائمة الديناميكي ] ---\

async def get_main_menu_keyboard(user_id):
    """بناء الأزرار بشكل آلي تماماً من الموديولات المحقونة"""
    keyboard = [["🚀 البحث عن شريك عشوائي"]]
    
    # جلب كافة الأزرار المسجلة في Config.DYNAMIC_BUTTONS
    dynamic_buttons = list(set(Config.DYNAMIC_BUTTONS.values()))
    
    # إزالة الأزرار الأساسية لتجنب التكرار
    excluded = ["🚀 البحث عن شريك عشوائي", "🏠 القائمة الرئيسية", "🛡️ فحص حالة الاشتراك وتفعيل البوت"]
    buttons_to_add = [btn for btn in dynamic_buttons if btn not in excluded]

    # توزيع الأزرار (2 في كل صف)
    for i in range(0, len(buttons_to_add), 2):
        keyboard.append(buttons_to_add[i:i+2])
    
    # إضافة زر لوحة التحكم للآدمن فقط
    if user_id == Config.ADMIN_ID:
        keyboard.append(["🛠️ لوحة المشرف"])
        
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- [ محرك الحقن السحري ] ---\

async def load_modules(application):
    """تحميل كافة الملفات من مجلد modules تلقائياً"""
    modules_dir = "modules"
    if not os.path.exists(modules_dir):
        os.makedirs(modules_dir)
        print(f"⚠️ المجلد {modules_dir} غير موجود، تم إنشاؤه.")
        return

    print("\n" + "═"*40)
    print("🚀 جاري حقن الأنظمة الملكية...")
    
    success_count = 0
    for filename in os.listdir(modules_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = f"modules.{filename[:-3]}"
            try:
                # استيراد الموديول
                module = importlib.import_module(module_name)
                # تشغيل وظيفة setup إذا وجدت
                if hasattr(module, 'setup'):
                    await module.setup(application)
                    # محاولة جلب الزر الرئيسي يدوياً إذا لم يسجل نفسه
                    if hasattr(module, 'MAIN_BUTTON'):
                        Config.DYNAMIC_BUTTONS[module_name] = module.MAIN_BUTTON
                    
                    print(f"✅ تم حقن: {filename}")
                    success_count += 1
            except Exception as e:
                print(f"❌ فشل تحميل {filename}: {e}")

    print(f"📊 إجمالي الأنظمة النشطة: {success_count}")
    print("═"*40 + "\n")

# --- [ المعالجات الأساسية ] ---\

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # 1. تسجيل المستخدم
    db.add_user(user_id=user.id, name=user.first_name, username=user.username)

    # 2. التحقق من الاشتراك الإجباري (من موديول subscription)
    try:
        from modules.subscription import is_subscribed
        subscribed = await is_subscribed(context.bot, user.id)
    except ImportError:
        subscribed = True # إذا لم يوجد ملف الاشتراك، اسمح بالدخول

    if not subscribed:
        # إذا لم يشترك، الموديول الخاص بالاشتراك سيتكفل بالرسالة عبر الـ TypeHandler
        return 

    # 3. إظهار القائمة الرئيسية (هنا الإبداع: القائمة تظهر فقط للمشتركين)
    kb = await get_main_menu_keyboard(user.id)
    
    await update.message.reply_text(
        f"👑 **أهلاً بك في العرش يا {user.first_name}**\n\n"
        "تم تفعيل كافة الأنظمة الملكية لك. اختر وجهتك الآن من الأسفل 👇",
        reply_markup=kb,
        parse_mode="Markdown"
    )

# --- [ تشغيل البوت ] ---\

def main():
    # فحص قاعدة البيانات
    if db.db is None:
        print("❌ لا يمكن البدء بدون قاعدة بيانات!")
        return

    application = Application.builder().token(Config.BOT_TOKEN).build()

    # تشغيل محرك الحقن قبل إضافة أي معالجات أخرى
    loop = asyncio.get_event_loop()
    loop.run_until_complete(load_modules(application))

    # إضافة أمر start
    application.add_handler(CommandHandler("start", start))

    print("⚡ البوت الآن قيد التشغيل بالقوة القصوى...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
