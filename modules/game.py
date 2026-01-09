import logging
import random
import asyncio
import os
import sys
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

# --- [ حل مشكلة المسارات لضمان العمل على جيت هاب ] ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from db import db
    from config import Config
except ImportError:
    logging.error("❌ فشل استيراد الملحقات الأساسية - تأكد من وجود db.py و config.py")

logger = logging.getLogger(__name__)

# --- [ الإعدادات الملكية ] ---
MAIN_BUTTON = "🕹️ منصة الألعاب 🕹️"
EXIT_GAMES = "🚫 مغادرة الألعاب"
GAME_POINTS = 6

# مخازن الألعاب
active_games = {} # {game_id: {data}}
waiting_queues = {"xo": [], "guess": [], "dice": []}

async def setup(application):
    # الحقن التلقائي في القائمة الرئيسية
    Config.DYNAMIC_BUTTONS[__name__] = MAIN_BUTTON
    
    # معالجة زر القائمة الرئيسي وزر الخروج
    application.add_handler(MessageHandler(filters.Regex(f"^{MAIN_BUTTON}$"), games_menu))
    application.add_handler(MessageHandler(filters.Regex(f"^{EXIT_GAMES}$"), exit_games))
    
    # معالجة ضغطات أزرار XO (Inline)
    application.add_handler(CallbackQueryHandler(handle_xo_clicks, pattern="^xo_"))
    
    # معالجة أزرار الألعاب الأساسية (النصية)
    game_filter = filters.Regex("^(❌⭕️ تحدي XO|🔢 تخمين الرقم|🎲 نرد الملوك)$")
    application.add_handler(MessageHandler(game_filter, handle_game_selection))
    
    # معالجة مدخلات لعبة التخمين
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^{EXIT_GAMES}|{MAIN_BUTTON}"), handle_guess_input), group=5)

# --- [ القائمة الرئيسية ] ---
async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        ["❌⭕️ تحدي XO", "🔢 تخمين الرقم"],
        ["🎲 نرد الملوك"],
        [EXIT_GAMES]
    ]
    await update.message.reply_text(
        "✨ **ساحة الألعاب الملكية المحدثة** ✨\n\n"
        "استمتع بتحدي أصدقائك الآن بالضغط على الأزرار أدناه.",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def exit_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from main import get_main_menu_keyboard
    kb = await get_main_menu_keyboard(update.effective_user.id)
    await update.message.reply_text("🏠 عدت إلى القائمة الرئيسية.", reply_markup=kb)

# --- [ معالجة اختيار الألعاب (حل مشكلة الاستجابة) ] ---
async def handle_game_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    gtype = ""
    if "XO" in text: gtype = "xo"
    elif "تخمين" in text: gtype = "guess"
    elif "نرد" in text: gtype = "dice"
    
    if user_id in waiting_queues[gtype]:
        await update.message.reply_text("⏳ أنت بالفعل في قائمة الانتظار، انتظر خصماً...")
        return

    waiting_queues[gtype].append(user_id)
    
    if len(waiting_queues[gtype]) >= 2:
        p1 = waiting_queues[gtype].pop(0)
        p2 = waiting_queues[gtype].pop(0)
        await start_session(context, gtype, p1, p2)
    else:
        await update.message.reply_text(f"🔍 جاري البحث عن خصم للعبة {text}... سنخبرك فور العثور عليه!")

# --- [ بدء اللعبة (Session) ] ---
async def start_xo_from_chat(context, p1, p2):
    """الوظيفة التي يتم استدعاؤها من ملف الدردشة"""
    await start_session(context, "xo", p1, p2)

async def start_session(context, gtype, p1, p2):
    gid = f"{p1}_{p2}_{int(time.time())}"
    active_games[gid] = {"type": gtype, "p1": p1, "p2": p2, "turn": p1}
    
    u1_data = db.get_user(p1)
    u2_data = db.get_user(p2)
    active_games[gid]["n1"] = u1_data.get("nickname", "الطرف الأول")
    active_games[gid]["n2"] = u2_data.get("nickname", "الطرف الثاني")

    if gtype == "xo":
        active_games[gid].update({"board": [" "] * 9, "sym": {p1: "❌", p2: "⭕️"}})
        await send_xo_board(context, gid)
    elif gtype == "guess":
        active_games[gid].update({"secret": random.randint(1, 100)})
        await context.bot.send_message(p1, "🎯 **بدأت لعبة التخمين!**\nالرقم بين 1-100. أرسل رقمك الآن.\n\n🟢 دورك أنت!")
        await context.bot.send_message(p2, f"🎯 **بدأت لعبة التخمين!**\nانتظر دور خصمك {active_games[gid]['n1']}.")
    elif gtype == "dice":
        await run_dice_game(context, gid)

# --- [ منطق لعبة XO ] ---
async def send_xo_board(context, gid, edit_id=None):
    g = active_games.get(gid)
    if not g: return
    
    kb = []
    for i in range(0, 9, 3):
        row = []
        for j in range(i, i+3):
            # مساحة كبيرة وشفافة
            val = g["board"][j] if g["board"][j] != " " else "⠀"
            row.append(InlineKeyboardButton(val, callback_data=f"xo_{gid}_{j}"))
        kb.append(row)

    for pid in [g["p1"], g["p2"]]:
        status = "🟢 دورك الآن!" if pid == g["turn"] else f"🔴 دور: {g['n2'] if pid == g['p1'] else g['n1']}"
        text = f"🎮 **تحدي الـ XO**\n\n{status}\nرمزك: {g['sym'][pid]}"
        
        try:
            if edit_id == pid:
                await context.bot.edit_message_text(chat_id=pid, message_id=g[f"m_{pid}"], text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            else:
                msg = await context.bot.send_message(pid, text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
                g[f"m_{pid}"] = msg.message_id
        except: pass

async def handle_xo_clicks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split("_")
    
    if len(data) < 3: return
    idx = int(data[-1])
    gid = "_".join(data[1:-1])
    
    g = active_games.get(gid)
    if not g or user_id != g["turn"] or g["board"][idx] != " ":
        await query.answer("⚠️ انتظر دورك أو اختر خانة فارغة!", show_alert=True)
        return

    g["board"][idx] = g["sym"][user_id]
    await query.answer()

    win_patterns = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    if any(g["board"][a] == g["board"][b] == g["board"][c] != " " for a,b,c in win_patterns):
        await end_game(context, gid, user_id)
    elif " " not in g["board"]:
        await end_game(context, gid, None)
    else:
        g["turn"] = g["p2"] if user_id == g["p1"] else g["p1"]
        await send_xo_board(context, gid, edit_id=g["p1"])
        await send_xo_board(context, gid, edit_id=g["p2"])

# --- [ لعبة التخمين والنرد ] ---
async def handle_guess_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    val = update.message.text
    if not val.isdigit(): return

    gid = next((k for k, v in active_games.items() if (v["p1"] == user_id or v["p2"] == user_id) and v["type"] == "guess"), None)
    if not gid: return
    
    g = active_games[gid]
    if user_id != g["turn"]: return
    
    val = int(val)
    partner = g["p2"] if user_id == g["p1"] else g["p1"]
    
    if val == g["secret"]:
        await end_game(context, gid, user_id)
    else:
        g["turn"] = partner
        hint = "أكبر ⬆️" if val < g["secret"] else "أصغر ⬇️"
        await update.message.reply_text(f"❌ تخمين خاطئ! الرقم الصحيح **{hint}**")
        await context.bot.send_message(partner, f"👤 خصمك خمن `{val}` وفشل.\n💡 تلميح: الرقم الصحيح **{hint}**\n\n🟢 **دورك الآن!**")

async def run_dice_game(context, gid):
    g = active_games[gid]
    for p in [g["p1"], g["p2"]]: await context.bot.send_message(p, "🎲 رمي النرد الملكي الآن...")
    d1 = await context.bot.send_dice(g["p1"])
    d2 = await context.bot.send_dice(g["p2"])
    await asyncio.sleep(4)
    if d1.dice.value > d2.dice.value: await end_game(context, gid, g["p1"])
    elif d2.dice.value > d1.dice.value: await end_game(context, gid, g["p2"])
    else:
        for p in [g["p1"], g["p2"]]: await context.bot.send_message(p, "🤝 تعادل!")
        active_games.pop(gid, None)

# --- [ إنهاء اللعبة ] ---
async def end_game(context, gid, winner_id):
    g = active_games.pop(gid, {})
    if not g: return
    
    if winner_id:
        loser_id = g["p2"] if winner_id == g["p1"] else g["p1"]
        db.update_points(winner_id, GAME_POINTS)
        db.update_points(loser_id, -int(GAME_POINTS/2))
        await context.bot.send_message(winner_id, f"🏆 **مبروك الفوز!** كسبت {GAME_POINTS} فلفل 🌶️")
        await context.bot.send_message(loser_id, f"💔 **حظ أوفر..** خسرت {int(GAME_POINTS/2)} فلفل 🌶️")
    else:
        for p in [g["p1"], g["p2"]]: await context.bot.send_message(p, "🤝 انتهت اللعبة بالتعادل!")
