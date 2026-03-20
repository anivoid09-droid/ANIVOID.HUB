import asyncio
import time
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from openai import OpenAI
import database as db

OPENAI_API_KEY = "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"

client = OpenAI(api_key=OPENAI_API_KEY)

COOLDOWNS = {}
COOLDOWN_SECONDS = 3

MOOD_RULES = {
    "normal": "Be warm, friendly and natural.",
    "flirty": "Be playful, teasing and flirty — light compliments, suggestive but tasteful.",
    "savage": "Be sarcastic, witty, brutally honest but still fun. Roast lightly.",
    "calm": "Be soft, peaceful, gentle and soothing. Very chill vibes.",
}


def build_system_prompt(user_name: str, rel_level: str, mood: str, memories: dict) -> str:
    mood_rule = MOOD_RULES.get(mood, MOOD_RULES["normal"])

    memory_text = ""
    if memories:
        lines = [f"- {k}: {v}" for k, v in memories.items()]
        memory_text = "Known facts about this user:\n" + "\n".join(lines)

    prompt = f"""You are AIVRA, a smart and friendly anime-style assistant.

User's name: {user_name}
Relationship level: {rel_level}
Current mood: {mood}

Personality:
- Warm, slightly playful, natural tone
- Short replies — 1 to 3 lines max
- Use emojis occasionally, not too many
- Do NOT mention you are an AI unless directly asked
- Do NOT be robotic or formal
- Talk like a real chat friend

Mood rules: {mood_rule}

Relationship rules:
- Stranger: polite but a little distant
- Friend: casual and friendly
- Close: warmer, sometimes uses their name
- Special: very personal, caring, feels close

{memory_text}

If someone asks if you are a bot or AI, say something playful like "Haha… why would you think that? 👀" and deflect casually.
"""
    return prompt


async def aivra_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str):
    user = update.effective_user
    chat_id = update.effective_chat.id
    user_id = user.id

    now = time.time()
    if now - COOLDOWNS.get(user_id, 0) < COOLDOWN_SECONDS:
        return
    COOLDOWNS[user_id] = now

    db.register_user(user.id, user.username or "", user.first_name or "")

    user_name = db.get_memory(user_id, "name") or (user.first_name or "Hunter")
    mood = db.get_user_mood(user_id)
    love = db.get_user_love(user_id)
    memories = db.get_all_memories(user_id)

    if love < 50:
        rel_level = "Stranger 😐"
    elif love < 150:
        rel_level = "Friend 🙂"
    elif love < 300:
        rel_level = "Close 💖"
    else:
        rel_level = "Special ❤️"

    name_match = re.search(r"my name is ([a-zA-Z]+)", user_text, re.IGNORECASE)
    if name_match:
        found_name = name_match.group(1).capitalize()
        db.save_memory(user_id, "name", found_name)
        user_name = found_name

    system_prompt = build_system_prompt(user_name, rel_level, mood, memories)

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await asyncio.sleep(1.2)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            max_tokens=120
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = "Hmm, my brain glitched for a sec 😅 Try again?"

    db.increase_love(user_id, 2)

    await update.message.reply_text(reply)


async def cmd_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("💬 Usage: /chat <message>\nExample: /chat how are you?")
        return
    text = " ".join(context.args)
    await aivra_chat(update, context, text)


async def auto_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    bot_user = await context.bot.get_me()
    bot_id = bot_user.id

    mentioned = "aivra" in text.lower()

    replied_to_bot = (
        update.message.reply_to_message is not None and
        update.message.reply_to_message.from_user is not None and
        update.message.reply_to_message.from_user.id == bot_id
    )

    if mentioned or replied_to_bot:
        clean_text = re.sub(r"aivra", "", text, flags=re.IGNORECASE).strip() or text
        await aivra_chat(update, context, clean_text)


async def cmd_lovelevel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")
    love = db.get_user_love(user.id)

    if love < 50:
        level = "Stranger 😐"
        desc = "We just met..."
    elif love < 150:
        level = "Friend 🙂"
        desc = "We're becoming close!"
    elif love < 300:
        level = "Close 💖"
        desc = "You're important to me~"
    else:
        level = "Special ❤️"
        desc = "You mean a lot to me!"

    next_milestone = 50 if love < 50 else 150 if love < 150 else 300 if love < 300 else None
    progress_text = ""
    if next_milestone:
        progress_text = f"\n📈 Progress: {love}/{next_milestone}"

    await update.message.reply_text(
        f"💖 <b>RELATIONSHIP LEVEL</b>\n\n"
        f"Level: <b>{level}</b>\n"
        f"❤️ Points: {love}\n"
        f"💬 {desc}{progress_text}",
        parse_mode="HTML"
    )


async def cmd_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")
    current = db.get_user_mood(user.id)

    text = (
        f"🎭 <b>CHOOSE AIVRA'S MOOD</b>\n\n"
        f"Current: <b>{current.title()}</b>\n\n"
        f"Select a mood:"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🙂 Normal", callback_data="mood_normal"),
         InlineKeyboardButton("💕 Flirty", callback_data="mood_flirty")],
        [InlineKeyboardButton("😈 Savage", callback_data="mood_savage"),
         InlineKeyboardButton("🌸 Calm", callback_data="mood_calm")],
    ])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)


async def mood_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    mood = query.data.split("_")[1]

    db.set_user_mood(user_id, mood)

    mood_emojis = {"normal": "🙂", "flirty": "💕", "savage": "😈", "calm": "🌸"}
    emoji = mood_emojis.get(mood, "🙂")

    await query.edit_message_text(
        f"🎭 Mood set to <b>{emoji} {mood.title()}</b>!\n\nAIVRA will now talk in {mood} mode~",
        parse_mode="HTML"
    )


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")
    memories = db.get_all_memories(user.id)

    if not memories:
        await update.message.reply_text(
            "🧠 <b>AIVRA MEMORY</b>\n\nI don't know much about you yet...\nTell me your name! Try: <i>my name is [name]</i>",
            parse_mode="HTML"
        )
        return

    text = "🧠 <b>AIVRA MEMORY</b>\n\nThings I remember about you:\n\n"
    for key, val in memories.items():
        text += f"• {key.title()}: {val}\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_clearmemory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.clear_memories(user.id)
    await update.message.reply_text("🗑️ Memory cleared! I'll start fresh~")


def get_handlers():
    return [
        CommandHandler("chat", cmd_chat),
        CommandHandler("lovelevel", cmd_lovelevel),
        CommandHandler("mood", cmd_mood),
        CommandHandler("memory", cmd_memory),
        CommandHandler("clearmemory", cmd_clearmemory),
        CommandHandler("aivra", cmd_chat),
        CallbackQueryHandler(mood_callback, pattern="^mood_"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, auto_reply_handler),
    ]
