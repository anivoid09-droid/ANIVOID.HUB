import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
import database as db
from utils.helpers import get_display_name, format_coins, format_time_remaining, battlepass_active


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        db.register_group(chat.id, chat.title or "Unknown Group")
    username = user.username or ""
    first_name = user.first_name or ""
    db.register_user(user.id, username, first_name)

    text = """🔥 <b>Welcome to ANIVOID RPG!</b>

🎮 <b>Game Commands:</b>

🗺 <b>Adventure:</b>
 /explore - Explore maps &amp; fight bosses
 /adventure - Go on adventure

⚔️ <b>Battle:</b>
 /raid - Start raid battle
 /damage - Check raid damage
 /cardfight - Fight another player

👥 <b>Guild:</b>
 /guildcreate - Create a guild
 /guildjoin - Join a guild
 /guildleave - Leave your guild
 /guildinfo - Guild information
 /raidboss - Start a guild raid
 /guildleaderboard - Guild rankings

🏆 <b>Tournament:</b>
 /tournament - View tournaments
 /jointournament - Join tournament
 /tournamentleaderboard - Tournament rankings

💰 <b>Economy:</b>
 /profile - View your profile
 /market - Open market
 /inventory - Your characters
 /cards - Your cards
 /bank - Bank balance
 /deposit &lt;amount&gt; - Deposit to bank
 /withdraw &lt;amount&gt; - Withdraw from bank

🎲 <b>Mini Games:</b>
 /dice - Roll dice
 /bet &lt;amount&gt; - Bet coins
 /rob @user - Rob someone
 /slots - Slot machine
 /flip - Coin flip

💎 <b>Premium:</b>
 /battlepass - View battle pass
 /buypass - Buy battle pass
 /mypremium - Check premium status

🎁 <b>Extras:</b>
 /lootbox - Open loot boxes
 /daily - Daily reward
 /leaderboard - Top 10 players
 /rank - Your rank

🤖 <b>AIVRA AI:</b>
 /chat &lt;msg&gt; - Chat with AIVRA
 /mood - Set AIVRA's mood
 /lovelevel - Check relationship level
 /memory - View what AIVRA remembers

🛡️ <b>Moderation (Groups):</b>
 /warn - Warn a user (reply)
 /warns - Check warnings
 /unwarn - Remove a warning
 /mute - Mute a user
 /unmute - Unmute a user

⚙️ <b>Admin:</b>
 /admins - Admin panel

Type any command to start! ⚡"""

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        db.register_group(chat.id, chat.title or "Unknown Group")
    username = user.username or ""
    first_name = user.first_name or ""
    data = db.register_user(user.id, username, first_name)

    bp_active = battlepass_active(data)
    bp_text = "✅ Active" if bp_active else "❌ Inactive"
    if bp_active:
        remaining = format_time_remaining(data['battlepass_expiry'])
        bp_text = f"✅ Active ({remaining} left)"

    dead_text = ""
    if data['is_dead'] and data['dead_until'] > time.time():
        dead_text = f"\n☠️ <b>Dead until:</b> {format_time_remaining(data['dead_until'])}"

    name = f"@{data['username']}" if data['username'] else data.get('first_name', 'Unknown')

    text = f"""👤 <b>PLAYER PROFILE</b>

🧑 <b>Name:</b> {name}
🆔 <b>ID:</b> {data['user_id']}
⭐ <b>Level:</b> {data['level']}
📊 <b>XP:</b> {format_coins(data['xp'])}
🏅 <b>Rank:</b> {data['rank']}
💰 <b>Wallet:</b> {format_coins(data['coins'])} coins
🏦 <b>Bank:</b> {format_coins(data['bank'])} coins
💎 <b>Battle Pass:</b> {bp_text}{dead_text}"""

    characters = db.get_user_characters(user.id)
    cards = db.get_user_cards(user.id)
    text += f"\n\n🧬 <b>Characters:</b> {len(characters)}\n🃏 <b>Cards:</b> {len(cards)}"

    guild = db.get_user_guild(user.id)
    if guild:
        text += f"\n🏰 <b>Guild:</b> {guild['name']}"

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")
    data = db.get_user(user.id)
    if not data:
        await update.message.reply_text("❌ Profile not found. Use /start first.")
        return

    name = f"@{data['username']}" if data['username'] else data.get('first_name', 'Unknown')

    all_users = db.get_all_users()
    position = next((i + 1 for i, u in enumerate(all_users) if u['user_id'] == user.id), None)

    text = f"""🏅 <b>YOUR RANK</b>

🧑 {name}
🎖️ <b>Rank:</b> {data['rank']}
⭐ <b>Level:</b> {data['level']}
📊 <b>XP:</b> {format_coins(data['xp'])}
🌍 <b>Global Position:</b> #{position or '?'} of {len(all_users)} players"""

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")
    data = db.get_user(user.id)
    if not data:
        await update.message.reply_text("❌ Use /start first.")
        return

    now = time.time()
    last_daily = data.get('last_daily', 0)
    cooldown = 86400  # 24 hours

    if now - last_daily < cooldown:
        remaining = cooldown - (now - last_daily)
        await update.message.reply_text(
            f"⏳ Daily reward already claimed!\nNext reward in: {format_time_remaining(now + remaining)}",
            parse_mode="HTML"
        )
        return

    from utils.helpers import battlepass_active
    reward = 1000
    xp_reward = 100
    if battlepass_active(data):
        reward = int(reward * 1.1)

    db.add_coins(user.id, reward)
    db.add_xp_and_level(user.id, xp_reward)
    db.update_user(user.id, last_daily=now)

    await update.message.reply_text(
        f"🎁 <b>DAILY REWARD CLAIMED!</b>\n\n💰 +{format_coins(reward)} coins\n📊 +{xp_reward} XP",
        parse_mode="HTML"
    )


async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")

    all_users = db.get_all_users()
    top = all_users[:10]

    if not top:
        await update.message.reply_text("❌ No players yet.")
        return

    text = "🏆 <b>TOP 10 HUNTERS</b>\n\n"
    from utils.helpers import medal
    for i, u in enumerate(top, 1):
        name = f"@{u['username']}" if u['username'] else u.get('first_name', 'Unknown')
        total = u['coins'] + u['bank']
        m = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{m} <b>{name}</b>\n"
        text += f"   Level: {u['level']} | XP: {format_coins(u['xp'])}\n"
        text += f"   Rank: {u['rank']}\n"
        text += f"   💰 {format_coins(total)} coins\n\n"

    await update.message.reply_text(text, parse_mode="HTML")


def get_handlers():
    return [
        CommandHandler("start", cmd_start),
        CommandHandler("help", cmd_start),
        CommandHandler("profile", cmd_profile),
        CommandHandler("rank", cmd_rank),
        CommandHandler("daily", cmd_daily),
        CommandHandler("leaderboard", cmd_leaderboard),
    ]
