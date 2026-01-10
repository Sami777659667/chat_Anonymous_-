import logging
import asyncio
import os
import sys
import time
import random
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

# --- [ نظام السجلات ] ---
game_logger = logging.getLogger("game_module")
handler = logging.FileHandler('game_errors.log', encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
game_logger.addHandler(handler)

# --- [ حل المسارات ] ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from db import db
    from config import Config
except Exception as e:
    game_logger.error(f"❌ فشل استيراد الأساسيات: {e}")

# --- [ الثوابت ] ---
MAIN_BUTTON = "🕹️ منصة الألعاب 🕹️"
GAME_BTNS = ["❌⭕️ تحدي XO", "🔢 تخمين الرقم", "🎲 نرد الملوك", "🎰 روليت الحظ"]
BACK_BTN = "🔙 رجوع"
CHAT_REQ_BTN = "💬 طلب فتح دردشة"
EXIT_GAMES = "🚫 مغادرة الألعاب"

active_games = {} 
waiting_queues = {k: [] for k in ["xo", "guess", "dice", "roulette"]}
user_to_game = {}

async def setup(application):
    Config.DYNAMIC_BUTTONS[__name__] = MAIN_BUTTON
    
    application.add_handler(MessageHandler(filters.Regex(f"^{MAIN_BUTTON}$") | filters.Regex(f"^{BACK_BTN}$"), games_menu), group=-1)
    application.add_handler(MessageHandler(filters.Regex(f"^{EXIT_GAMES}$"), exit_games), group=-1)
    application.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(GAME_BTNS)})$"), handle_search), group=-1)
    application.add_handler(MessageHandler(filters.Regex(f"^{CHAT_REQ_BTN}$"), request_chat_bridge), group=-1)
    
    # معالج الدردشة المتبخرة (أولوية عالية لمعالجة رسائل اللعب)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_game_chat), group=1)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess_input), group=2)
    
    application.add_handler(CallbackQueryHandler(game_callbacks, pattern=r"^(xo|gc|sh)\|"))

# --- [ ميزة تبخير الرسائل (7 ثوانٍ) ] ---
async def delete_after_delay(context, chat_id, message_id, delay=7):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except:
        pass

async def handle_game_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    from modules.chat import active_chats
    
    # إذا كان المستخدم في دردشة مرتبطة بلعبة
    if uid in active_chats and uid in user_to_game:
        partner_id = active_chats[uid]
        text = update.message.text
        
        # إرسال الرسالة للخصم مع وسم الدردشة
        msg_to_partner = await context.bot.send_message(partner_id, f"💬 الخصم: {text}")
        msg_to_self = update.message # الرسالة التي أرسلها المستخدم نفسه
        
        # جدولة التبخير بعد 7 ثوانٍ للرسالتين
        asyncio.create_task(delete_after_delay(context, partner_id, msg_to_partner.message_id))
        asyncio.create_task(delete_after_delay(context, uid, msg_to_self.message_id))
        
        return # التوقف هنا لكي لا تذهب الرسالة لمعالج التخمين

# --- [ القوائم والواجهات ] ---

async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [GAME_BTNS[0:2], GAME_BTNS[2:4], [EXIT_GAMES]]
    await update.message.reply_text(
        "✨ **ساحة التحديات الملكية** ✨\n\nالفائز +6 🌶️ | الخاسر -3 🌶️\nالعب واكسب واحذر من تبخر الرسائل! 🔥",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def exit_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from main import get_main_menu_keyboard
    await update.message.reply_text("🏠 العودة للمملكة..", reply_markup=await get_main_menu_keyboard(update.effective_user.id))

# --- [ البحث ونظام الإحالة ] ---

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    choice = update.message.text
    
    if db.get_points(user_id) < 3:
        return await show_insufficient_pepper(update, context)

    gtype = "xo" if "XO" in choice else "guess" if "تخمين" in choice else "dice" if "نرد" in choice else "roulette"
    if user_id in waiting_queues[gtype]: return

    waiting_queues[gtype].append(user_id)
    
    bot_username = (await context.bot.get_me()).username
    share_text = f"أتحداك في {choice}! 🔥\nلو فزت عليّ لك 10 نجوم ⭐ و 70 فلفل 🌶️.. وريني لعبك! 💪"
    invite_url = f"https://t.me/share/url?url=https://t.me/{bot_username}?start=ref_{user_id}&text={share_text}"
    
    kb = [[InlineKeyboardButton("🎮 اللعب مع صديق 10⭐", url=invite_url)]]
    await update.message.reply_text(
        "🔍 **جاري البحث عن خصم...**\n⏳ انتظر أو شارك الرابط لخويك واكسب 70 فلفل 🌶️ و 10 نجوم ⭐!",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    if len(waiting_queues[gtype]) >= 2:
        p1, p2 = waiting_queues[gtype].pop(0), waiting_queues[gtype].pop(0)
        await start_match(context, gtype, p1, p2)

# --- [ منطق XO الذهبي المستقر ] ---

def build_xo_keyboard(g, gid):
    kb = []
    for i in range(0, 16, 4):
        row = [InlineKeyboardButton(g["board"][j] if g["board"][j] != " " else "⠀", callback_data=f"xo|{gid}|{j}") for j in range(i, i+4)]
        kb.append(row)
    kb.append([InlineKeyboardButton(CHAT_REQ_BTN, callback_data=f"gc|req|{gid}")])
    return InlineKeyboardMarkup(kb)

async def update_xo_ui(context, gid):
    g = active_games.get(gid)
    if not g: return
    for uid in [g["p1"], g["p2"]]:
        is_turn = (uid == g["turn"])
        opponent = g['n2'] if uid == g['p1'] else g['n1']
        text = f"🎮 **تحدي XO 4x4**\n👤 الخصم: {opponent}\n\n"
        text += "🟢 **دورك الحين..**" if is_turn else f"⏳ **انتظر خصمك ({opponent})..**"
        try:
            await context.bot.edit_message_text(chat_id=uid, message_id=g["msg_ids"][uid], text=text, reply_markup=build_xo_keyboard(g, gid))
        except: pass

async def game_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("|")
    action, uid = data[0], query.from_user.id
    
    try:
        if action == "xo":
            gid, idx = data[1], int(data[2])
            g = active_games.get(gid)
            if not g: return await query.answer("انتهت اللعبة! 🏁")
            if uid != g["turn"]: return await query.answer("عفواً.. مو دورك! ⏳\nلا تكرر الضغط عشان ما تنحظر 🚫", show_alert=True)
            if g["board"][idx] != " ": return await query.answer("المربع محجوز! ❌")

            await query.answer(cache_time=0)
            g["board"][idx] = g["sym"][uid]
            g["turn"] = g["p2"] if uid == g["p1"] else g["p1"]
            
            if check_win_4x4(g["board"]): await end_game_logic(context, gid, uid)
            elif " " not in g["board"]: await end_game_logic(context, gid, None)
            else: await update_xo_ui(context, gid)

        elif action == "gc":
            sub, gid = data[1], data[2]
            g = active_games.get(gid)
            if not g: return await query.answer("انتهت اللعبة")
            if sub == "req":
                target = g["p2"] if uid == g["p1"] else g["p1"]
                await query.answer("تم إرسال طلب الدردشة المتبخرة..")
                kb = [[InlineKeyboardButton("✅ قبول", callback_data=f"gc|acc|{gid}"), InlineKeyboardButton("❌ رفض", callback_data=f"gc|dec|{gid}")]]
                await context.bot.send_message(target, "💬 خصمك يبي يفتح دردشة (تتبخر كل 7 ثوانٍ)، توافق؟", reply_markup=InlineKeyboardMarkup(kb))
            elif sub == "acc":
                from modules.chat import active_chats
                active_chats[g["p1"]], active_chats[g["p2"]] = g["p2"], g["p1"]
                await query.message.edit_text("✅ تم ربط الدردشة! الرسائل ستختفي بعد 7 ثوانٍ.")
                await context.bot.send_message(g["p1"] if uid == g["p2"] else g["p2"], "✅ وافق الخصم! الدردشة المتبخرة تعمل الآن.")

    except Exception:
        game_logger.error(f"Callback Error: {traceback.format_exc()}")

# --- [ بقية الألعاب والوظائف ] ---

async def handle_guess_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_to_game: return
    gid = user_to_game[uid]; g = active_games.get(gid)
    if not g or g["type"] != "guess": return
    if uid != g["turn"]: return await update.message.reply_text("⏳ **مو دورك!**")
    if not update.message.text.isdigit(): return
    val = int(update.message.text); partner = g["p2"] if uid == g["p1"] else g["p1"]
    if val == g["target"]: await end_game_logic(context, gid, uid)
    else:
        g["turn"] = partner
        hint = "أكبر ⬆️" if val < g["target"] else "أصغر ⬇️"
        await update.message.reply_text(f"❌ خطأ! الرقم {hint}")
        await context.bot.send_message(partner, f"🎯 الخصم خمن {val} وطلع خطأ!\n🟢 **دورك: خمن رقم بين 1 و 100**")

async def end_game_logic(context, gid, win_id):
    g = active_games.pop(gid, {})
    if not g: return
    p1, p2 = g["p1"], g["p2"]
    user_to_game.pop(p1, None); user_to_game.pop(p2, None)
    try:
        from modules.chat import active_chats
        active_chats.pop(p1, None); active_chats.pop(p2, None)
    except: pass
    for uid in [p1, p2]:
        res = ("🏆 كفو! فزت بـ 6 🌶️" if uid == win_id else "💀 هاردلك.. خسرت 3 🌶️") if win_id else "🤝 تعادل!"
        final_text = f"🏁 **انتهت المباراة!**\n\n{res}\nتم إغلاق الدردشة."
        if g["type"] == "xo":
            try: await context.bot.edit_message_text(chat_id=uid, message_id=g["msg_ids"][uid], text=final_text)
            except: await context.bot.send_message(uid, final_text)
        else: await context.bot.send_message(uid, final_text)
        if win_id: db.update_points(uid, 6 if uid == win_id else -3)

async def start_match(context, gtype, p1, p2):
    gid = str(int(time.time() * 1000))[-8:]
    u1, u2 = db.get_user(p1), db.get_user(p2)
    n1, n2 = u1.get("nickname", "بطل"), u2.get("nickname", "بطل")
    active_games[gid] = {"type": gtype, "p1": p1, "p2": p2, "turn": p1, "n1": n1, "n2": n2, "msg_ids": {}}
    user_to_game[p1], user_to_game[p2] = gid, gid
    if gtype == "xo":
        active_games[gid].update({"board": [" "] * 16, "sym": {p1: "❌", p2: "⭕️"}})
        for uid in [p1, p2]:
            opponent = n2 if uid == p1 else n1
            text = f"🎮 **تحدي XO 4x4**\n👤 الخصم: {opponent}\n\n" + ("🟢 **دورك..**" if uid == p1 else "⏳ **انتظر..**")
            msg = await context.bot.send_message(uid, text, reply_markup=build_xo_keyboard(active_games[gid], gid))
            active_games[gid]["msg_ids"][uid] = msg.message_id
    elif gtype == "guess":
        active_games[gid]["target"] = random.randint(1, 100)
        await context.bot.send_message(p1, f"🎯 **ضد {n2}**\n🟢 **دورك (1-100):**"); await context.bot.send_message(p2, f"🎯 **ضد {n1}**\n⏳ **انتظر خصمك..**")
    elif gtype == "dice": await run_dice(context, gid)
    elif gtype == "roulette": await run_roulette(context, gid)

def check_win_4x4(b):
    p = []
    for i in range(0, 16, 4): p.append((i, i+1, i+2, i+3))
    for i in range(4): p.append((i, i+4, i+8, i+12))
    p.extend([(0, 5, 10, 15), (3, 6, 9, 12)])
    return any(b[x[0]] == b[x[1]] == b[x[2]] == b[x[3]] != " " for x in p)

async def run_dice(context, gid):
    g = active_games[gid]
    d1 = await context.bot.send_dice(g["p1"]); d2 = await context.bot.send_dice(g["p2"])
    await asyncio.sleep(4); await end_game_logic(context, gid, g["p1"] if d1.dice.value > d2.dice.value else g["p2"] if d2.dice.value > d1.dice.value else None)

async def run_roulette(context, gid):
    g = active_games[gid]
    s1 = await context.bot.send_dice(g["p1"], emoji="🎰"); s2 = await context.bot.send_dice(g["p2"], emoji="🎰")
    await asyncio.sleep(4); await end_game_logic(context, gid, g["p1"] if s1.dice.value > s2.dice.value else g["p2"])

async def show_insufficient_pepper(update, context):
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/share/url?url=https://t.me/{bot_username}?start=ref_{user_id}&text=أتحداك تهزمني!"
    await update.message.reply_text("⚠️ **رصيدك طايح!** (تحتاج 3 فلفل).\nشارك رابطك واكسب 70 فلفل 🌶️ و 10 نجوم 🌟!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 مشاركة الرابط", url=ref_link)]]))

async def request_chat_bridge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    gid = user_to_game.get(uid)
    if not gid: return
    g = active_games.get(gid)
    partner = g["p2"] if uid == g["p1"] else g["p1"]
    kb = [[InlineKeyboardButton("✅ قبول", callback_data=f"gc|acc|{gid}"), InlineKeyboardButton("❌ رفض", callback_data=f"gc|dec|{gid}")]]
    await context.bot.send_message(partner, "💬 خصمك يبي يسولف (دردشة متبخرة)، تم؟", reply_markup=InlineKeyboardMarkup(kb))
