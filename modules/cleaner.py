import logging
import asyncio
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

logger = logging.getLogger(__name__)

async def setup(application):
    # إضافة معالج لتنظيف أزرار الـ Inline (مثل الألعاب والمكافآت)
    # ملاحظة: تم حذف 'group' لمنع الخطأ الذي ظهر عندك في الكونسول
    application.add_handler(CallbackQueryHandler(magic_inline_cleaner))
    
    # معالج ذكي: إذا أرسل المستخدم أي نص، نقوم بحذف أزرار القائمة السفلية القديمة إذا لزم الأمر
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_remove_reply_markup))

async def magic_inline_cleaner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف رسالة الزر فور الضغط عليه (التبخر السحري)"""
    query = update.callback_query
    
    # الأزرار التي نريدها أن تختفي بمجرد النقر (يمكنك إضافة المزيد هنا)
    buttons_to_clean = ["join_xo", "join_guess", "claim_h", "claim_d", "cancel_search"]
    
    if query.data in buttons_to_clean:
        try:
            # حذف الرسالة التي تحتوي على الزر ليبقى الشات نظيفاً
            await query.delete_message()
            await query.answer("🪄 تم المسح السحري!")
        except Exception as e:
            logger.warning(f"لم يتمكن البوت من حذف الرسالة: {e}")

async def clean_chat_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وظيفة اختيارية لحذف آخر X رسائل من البوت (تطهير شامل)"""
    chat_id = update.effective_chat.id
    message_id = update.effective_message.message_id
    
    for i in range(message_id, message_id - 10, -1):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=i)
        except:
            continue
