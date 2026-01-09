import asyncio
import random
import logging
import os
import sys
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters

# --- [ إعدادات المسارات ] ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from db import db
    from config import Config
except ImportError:
    logging.error("❌ فشل استيراد الملحقات الأساسية")

logger = logging.getLogger(__name__)

# --- [ تعريف الأزرار - التأكد من المطابقة التامة ] ---
MAIN_BUTTON = "💫 غرف الدردشة 💫"
ROOM_PUBLIC = "🌍 الغرفة العامة (مجانية)"
ROOM_GIRLS = "👸 الغرفة الملكية (VIP)"
EXIT_ROOM = "🔙 مغادرة الغرف"
DISCUSSION_URL = "https://t.me/Anonymousa_Arabic"
VIP_URL = "https://t.me/+nX72izXBXVEzMDNk"

# مخازن الحالة
active_rooms = {"public": set(), "girls": set()}
user_current_room = {} 

# --- [ نظام الأرواح الذكية (المستخدمين الوهميين) ] ---
FAKE_USERS = [
    {"name": "ليان ✨", "gender": "female", "msgs": ["نورتوا الغرفة يا حلوين 😍", "أرحبوااا تراحيب المطر", "هلا والله 🌹", "كيفكم اليوم؟"]},
    {"name": "صقر الجنوب 🦅", "gender": "male", "msgs": ["يا هلا بالنشامى 👑", "منور يا وحش ✨", "ارحب ارحب", "صح لسانك"]},
    {"name": "ريماس 🎀", "gender": "female", "msgs": ["يا زين السوالف معكم 🌹", "هههههههههه الله يسعدك", "كلامك عسل", "نورت الغرفة"]},
    {"name": "فهد الملوكي 👑", "gender": "male", "msgs": ["وينكم يا جماعة؟ 🧐", "الغرفة منورة بوجودكم", "أحد عنده سالفة؟ 🎤", "يا هلا وغلا"]}
]

async def setup(application):
    Config.DYNAMIC_BUTTONS[__name__] = MAIN_BUTTON
    
    # معالجة الأزرار (استخدام Regex لضمان الدقة)
    application.add_handler(MessageHandler(filters.Regex(f"^{MAIN_BUTTON}$"), show_rooms_menu))
    application.add_handler(MessageHandler(filters.Regex(f"^{EXIT_ROOM}$"), leave_room))
    application.add_handler(MessageHandler(filters.Regex(r"🌍 الغرفة العامة"), lambda u, c: join_room(u, c, "public")))
    application.add_handler(MessageHandler(filters.Regex(r"👸 الغرفة الملكية"), lambda u, c: join_room(u, c, "girls")))
    
    # محرك الدردشة الذكي
    room_msg_filter = filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({ROOM_PUBLIC}|{ROOM_GIRLS}|{EXIT_ROOM}|🏠)")
    application.add_handler(MessageHandler(room_msg_filter, handle_chat))

# --- [ القائمة الرئيسية ] ---
async def show_rooms_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[ROOM_PUBLIC], [ROOM_GIRLS], [EXIT_ROOM]]
    ikb = [[InlineKeyboardButton("💬 مجموعة النقاش", url=DISCUSSION_URL)]]
    
    await update.message.reply_text(
        "🏰 **مرحباً بك في مجمع الغرف الملكي**\n\n"
        "عالم من المرح والدردشة بانتظارك.. اختر غرفتك المفضلة الآن واستمتع بالأجواء!",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    await update.message.reply_text("🔗 روابط تهمك:", reply_markup=InlineKeyboardMarkup(ikb))

# --- [ منطق الانضمام والترحيب ] ---
async def join_room(update: Update, context: ContextTypes.DEFAULT_TYPE, room_id):
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    nick = user_data.get("nickname", "نخبة ✨")

    # نظام تقييد غرفة البنات/VIP
    if room_id == "girls":
        is_vip = user_data.get("is_vip", False)
        ref_count = user_data.get("referred_count", 0)
        gender = user_data.get("gender", "")
        
        if not (is_vip or ref_count >= 2 or "أنثى" in gender):
            ref_link = f"https://t.me/{(await context.bot.get_me()).username}?start=ref_{user_id}"
            msg = (
                "👸 **عذراً يا مبدع، هذه الغرفة مخصصة للنخبة!**\n\n"
                "لتتمكن من الانضمام لهذه الأجواء الخاصة، يرجى:\n"
                "✅ دعوة **صديقين (2)** للبوت عبر رابطك.\n"
                "✅ أو الحصول على عضوية **VIP** الملكية.\n\n"
                f"🔗 رابطك: `{ref_link}`"
            )
            ikb = [[InlineKeyboardButton("👑 تفعيل VIP عبر المشرف", url=VIP_URL)]]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(ikb), parse_mode="Markdown")
            return

    user_current_room[user_id] = room_id
    active_rooms[room_id].add(user_id)
    
    # إحصائيات الغرفة الحيوية
    fake_count = random.randint(3, 7)
    total_count = len(active_rooms[room_id]) + fake_count
    
    # جلب أسماء الحضور (حقيقيين + وهميين)
    real_names = [db.get_user(uid).get("nickname", "عضو") for uid in list(active_rooms[room_id])[:5]]
    fake_names = [f["name"] for f in random.sample(FAKE_USERS, 3)]
    all_names = ", ".join(real_names + fake_names)

    await update.message.reply_text(
        f"✅ **تم دخولك إلى {ROOM_PUBLIC if room_id == 'public' else ROOM_GIRLS}**\n\n"
        f"👥 المتواجدون الآن: `{total_count}` مستخدم\n"
        f"💬 أبرز الحضور: {all_names}\n\n"
        "أهلاً بك! ابدأ الدردشة الآن (يمكنك السحب للرد على أي رسالة).",
        reply_markup=ReplyKeyboardMarkup([[EXIT_ROOM]], resize_keyboard=True),
        parse_mode="Markdown"
    )
    
    await broadcast(context, room_id, f"✨ انضم الشريك المبدع **{nick}** لساحتنا الآن!", exclude_id=user_id)

# --- [ محرك الدردشة والتفاعل ] ---
async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    room_id = user_current_room.get(user_id)
    if not room_id: return

    user_data = db.get_user(user_id)
    nick = user_data.get("nickname", "مجهول")
    text = update.message.text

    # بث الرسالة للجميع (مع دعم الرد بالسحب)
    msg_template = f"👤 **{nick}**: {text}"
    await broadcast(context, room_id, msg_template, exclude_id=user_id)

    # تفاعل "الأرواح الذكية" (Bots)
    if any(word in text for word in ["مرحبا", "هلا", "سلام", "هلو", "كيفكم"]):
        await asyncio.sleep(random.uniform(1.5, 3.5))
        fake = random.choice(FAKE_USERS)
        reply = random.choice(fake["msgs"])
        await broadcast(context, room_id, f"👤 **{fake['name']}**: {reply}")

# --- [ وظيفة البث الذكي ] ---
async def broadcast(context, room_id, text, exclude_id=None):
    targets = list(active_rooms.get(room_id, set()))
    for uid in targets:
        if uid == exclude_id: continue
        try:
            await context.bot.send_message(uid, text, parse_mode="Markdown")
        except:
            active_rooms[room_id].discard(uid)

# --- [ مغادرة الغرفة ] ---
async def leave_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    room_id = user_current_room.pop(user_id, None)
    
    if room_id:
        active_rooms[room_id].discard(user_id)
        nick = db.get_user(user_id).get("nickname", "عضو")
        await broadcast(context, room_id, f"👋 الشريك **{nick}** غادرنا الآن، ننتظر عودته!")
    
    from main import get_main_menu_keyboard
    await update.message.reply_text("🏠 عدت إلى القائمة الرئيسية للمملكة.", reply_markup=await get_main_menu_keyboard(user_id))
