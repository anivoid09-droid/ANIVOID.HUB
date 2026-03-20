import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import database as db
from utils.helpers import format_coins, format_time_remaining, is_character_dead, battlepass_active, get_display_name_from_db
from config import GUILD_CREATE_COST, GUILD_MAX_MEMBERS


async def cmd_guild_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        db.register_group(chat.id, chat.title or "Unknown Group")
    db.register_user(user.id, user.username or "", user.first_name or "")

    existing = db.get_user_guild(user.id)
    if existing:
        await update.message.reply_text(
            f"❌ You're already in a guild: <b>{existing['name']}</b>\n"
            f"Leave it first with /guildleave",
            parse_mode="HTML"
        )
        return

    data = db.get_user(user.id)
    total = (data['coins'] or 0) + (data['bank'] or 0)
    if total < GUILD_CREATE_COST:
        await update.message.reply_text(
            f"❌ Creating a guild costs <b>{format_coins(GUILD_CREATE_COST)}</b> coins.\n"
            f"You have: {format_coins(total)} coins",
            parse_mode="HTML"
        )
        return

    if context.args:
        guild_name = " ".join(context.args).strip()
        await _create_guild(update, context, guild_name)
    else:
        context.user_data['state'] = 'awaiting_guild_name'
        await update.message.reply_text(
            f"🏰 Creating a guild costs <b>{format_coins(GUILD_CREATE_COST)}</b> coins.\n\n"
            f"Please reply with the name for your guild:",
            parse_mode="HTML"
        )


async def _create_guild(update, context, guild_name):
    user = update.effective_user
    if not guild_name or len(guild_name) < 3:
        await update.message.reply_text("❌ Guild name must be at least 3 characters!")
        return
    if len(guild_name) > 30:
        await update.message.reply_text("❌ Guild name must be under 30 characters!")
        return

    data = db.get_user(user.id)
    if not db.deduct_coins(user.id, GUILD_CREATE_COST):
        await update.message.reply_text("❌ Not enough coins!")
        return

    try:
        guild_id = db.create_guild(guild_name, user.id)
        context.user_data.pop('state', None)
        await update.message.reply_text(
            f"🏰 <b>GUILD CREATED!</b>\n\n"
            f"🏷️ Name: <b>{guild_name}</b>\n"
            f"👑 Leader: @{user.username or user.first_name}\n"
            f"👥 Members: 1/{GUILD_MAX_MEMBERS}\n"
            f"💰 Cost: {format_coins(GUILD_CREATE_COST)} coins deducted\n\n"
            f"Invite members with /guildinfo!",
            parse_mode="HTML"
        )
    except Exception as e:
        db.add_coins(user.id, GUILD_CREATE_COST)
        await update.message.reply_text(f"❌ Failed to create guild. Name may already be taken!")


async def cmd_guild_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")

    guild = db.get_user_guild(user.id)
    if not guild:
        await update.message.reply_text(
            "❌ You're not in a guild!\n"
            "Create one with /guildcreate or ask to be invited."
        )
        return

    members = db.get_guild_members(guild['guild_id'])
    leader = db.get_user(guild['leader_id'])
    leader_name = get_display_name_from_db(leader) if leader else "Unknown"

    member_list = ""
    for m in members[:10]:
        name = f"@{m['username']}" if m['username'] else m.get('first_name', 'Unknown')
        role_emoji = "👑" if m['role'] == 'Leader' else "⚔️"
        member_list += f"{role_emoji} {name} (Lv.{m['level']})\n"

    if len(members) > 10:
        member_list += f"...and {len(members) - 10} more"

    text = (
        f"🏰 <b>GUILD: {guild['name']}</b>\n\n"
        f"👑 Leader: {leader_name}\n"
        f"👥 Members: {len(members)}/{GUILD_MAX_MEMBERS}\n"
        f"🏆 Guild Points: {format_coins(guild['guild_points'])}\n\n"
        f"<b>Members:</b>\n{member_list}"
    )

    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚔️ Guild Raid", callback_data="guild_raid_start"),
        InlineKeyboardButton("🚪 Leave", callback_data="guild_leave_confirm"),
    ]])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)


async def cmd_guild_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")

    existing = db.get_user_guild(user.id)
    if existing:
        await update.message.reply_text(f"❌ You're already in guild: <b>{existing['name']}</b>", parse_mode="HTML")
        return

    guilds = db.get_all_guilds()
    if not guilds:
        await update.message.reply_text("❌ No guilds available. Create one with /guildcreate!")
        return

    context.user_data['guild_list'] = guilds
    context.user_data['guild_list_index'] = 0
    await show_guild_list(update, context, 0, is_callback=False)


async def show_guild_list(update, context, index, is_callback=False):
    guilds = context.user_data.get('guild_list', [])
    if not guilds:
        return

    text = f"🏰 <b>GUILDS LIST</b>\n\n"
    start = index * 5
    end = min(start + 5, len(guilds))
    page_guilds = guilds[start:end]

    rows = []
    for i, g in enumerate(page_guilds):
        count = db.get_guild_member_count(g['guild_id'])
        text += f"{start + i + 1}. <b>{g['name']}</b> — {count}/{GUILD_MAX_MEMBERS} members, {format_coins(g['guild_points'])} pts\n"
        if count < GUILD_MAX_MEMBERS:
            rows.append([InlineKeyboardButton(f"Join {g['name']}", callback_data=f"guild_join_{g['guild_id']}")])

    nav_row = []
    if start > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"guild_list_prev_{index}"))
    if end < len(guilds):
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"guild_list_next_{index}"))
    if nav_row:
        rows.append(nav_row)

    buttons = InlineKeyboardMarkup(rows) if rows else None

    if is_callback:
        query = update.callback_query
        try:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)
        except Exception:
            await query.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)


async def cmd_guild_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")

    guild = db.get_user_guild(user.id)
    if not guild:
        await update.message.reply_text("❌ You're not in a guild!")
        return

    if guild['leader_id'] == user.id:
        await update.message.reply_text(
            "❌ You're the leader! You can't leave.\n"
            "Transfer leadership or disband the guild first."
        )
        return

    db.leave_guild(guild['guild_id'], user.id)
    await update.message.reply_text(f"✅ You left <b>{guild['name']}</b>.", parse_mode="HTML")


async def cmd_guild_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guilds = db.get_all_guilds()[:10]
    if not guilds:
        await update.message.reply_text("❌ No guilds yet!")
        return

    text = "🏰 <b>TOP GUILDS</b>\n\n"
    for i, g in enumerate(guilds, 1):
        count = db.get_guild_member_count(g['guild_id'])
        m = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{m} <b>{g['name']}</b>\n   👥 {count} members | 🏆 {format_coins(g['guild_points'])} pts\n\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_raidboss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")

    guild = db.get_user_guild(user.id)
    if not guild:
        await update.message.reply_text("❌ You're not in a guild!")
        return

    if guild['leader_id'] != user.id:
        await update.message.reply_text("❌ Only the guild leader can start a guild raid!")
        return

    existing = db.get_active_guild_raid(guild['guild_id'])
    if existing:
        await update.message.reply_text(f"❌ Guild raid already active! Status: {existing['status']}")
        return

    guild_bosses = db.get_bosses_by_type('guild_boss')
    if not guild_bosses:
        await update.message.reply_text("❌ No guild bosses available! Admin needs to add guild bosses.")
        return

    boss = guild_bosses[0]
    raid_id = db.create_guild_raid(guild['guild_id'], boss['boss_id'])
    context.user_data['guild_raid_id'] = raid_id

    members = db.get_guild_members(guild['guild_id'])

    member_text = ""
    for m in members[:15]:
        name = f"@{m['username']}" if m['username'] else m.get('first_name', 'Unknown')
        member_text += f"• {name} (Lv.{m['level']})\n"

    text = (
        f"🐉 <b>GUILD RAID STARTING!</b>\n\n"
        f"🏰 Guild: <b>{guild['name']}</b>\n"
        f"👹 Boss: <b>{boss['name']}</b>\n"
        f"💪 Boss Power: {format_coins(boss['power'])}\n"
        f"❤️ Boss Health: {format_coins(boss['health'])}\n"
        f"💰 Total Reward: {format_coins(boss['rewards'])} coins\n\n"
        f"<b>Guild Members:</b>\n{member_text}\n"
        f"Members, press the button to join the raid!"
    )

    join_btn = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚔️ Join Guild Raid!", callback_data=f"graid_join_{raid_id}")
    ], [
        InlineKeyboardButton("🚀 Start Fight (Leader)", callback_data=f"graid_fight_{raid_id}")
    ]])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=join_btn)


async def guild_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("guild_join_"):
        guild_id = int(data.split("_")[-1])
        existing = db.get_user_guild(user_id)
        if existing:
            await query.answer("You're already in a guild!", show_alert=True)
            return
        count = db.get_guild_member_count(guild_id)
        if count >= GUILD_MAX_MEMBERS:
            await query.answer("This guild is full!", show_alert=True)
            return
        db.join_guild(guild_id, user_id)
        conn_guild = db.get_conn()
        g = conn_guild.execute("SELECT name FROM guilds WHERE guild_id = ?", (guild_id,)).fetchone()
        conn_guild.close()
        gname = g['name'] if g else "Unknown"
        await query.answer(f"Joined {gname}!", show_alert=True)
        try:
            await query.edit_message_text(f"✅ You joined <b>{gname}</b>!", parse_mode="HTML")
        except Exception:
            pass

    elif data.startswith("guild_list_prev_"):
        index = max(0, int(data.split("_")[-1]) - 1)
        await show_guild_list(update, context, index, is_callback=True)

    elif data.startswith("guild_list_next_"):
        index = int(data.split("_")[-1]) + 1
        await show_guild_list(update, context, index, is_callback=True)

    elif data == "guild_leave_confirm":
        guild = db.get_user_guild(user_id)
        if not guild:
            await query.answer("You're not in a guild!")
            return
        if guild['leader_id'] == user_id:
            await query.answer("Leaders can't leave!", show_alert=True)
            return
        db.leave_guild(guild['guild_id'], user_id)
        await query.edit_message_text(f"✅ You left <b>{guild['name']}</b>.", parse_mode="HTML")

    elif data.startswith("graid_join_"):
        raid_id = int(data.split("_")[-1])
        guild = db.get_user_guild(user_id)
        if not guild:
            await query.answer("You're not in a guild!", show_alert=True)
            return

        chars = db.get_user_characters(user_id)
        alive_chars = [c for c in chars if not is_character_dead(c)]
        if not alive_chars:
            await query.answer("You have no alive characters!", show_alert=True)
            return

        context.user_data['graid_id'] = raid_id
        context.user_data['graid_chars'] = alive_chars
        context.user_data['graid_char_index'] = 0
        await show_graid_char(update, context, 0, alive_chars, raid_id)

    elif data.startswith("graid_char_prev_"):
        parts = data.split("_")
        index = max(0, int(parts[-1]) - 1)
        raid_id = context.user_data.get('graid_id')
        chars = context.user_data.get('graid_chars', [])
        await show_graid_char(update, context, index, chars, raid_id)

    elif data.startswith("graid_char_next_"):
        parts = data.split("_")
        index = int(parts[-1]) + 1
        raid_id = context.user_data.get('graid_id')
        chars = context.user_data.get('graid_chars', [])
        index = min(len(chars) - 1, index)
        await show_graid_char(update, context, index, chars, raid_id)

    elif data.startswith("graid_char_select_"):
        parts = data.split("_")
        raid_id = int(parts[3])
        index = int(parts[4])
        chars = context.user_data.get('graid_chars', [])
        if not chars or index >= len(chars):
            await query.answer("Session expired!")
            return
        char = chars[index]
        db.join_guild_raid(raid_id, user_id, char['char_id'])
        await query.edit_message_text(
            f"✅ <b>{char['name']}</b> joined the guild raid!\n\nWaiting for others...",
            parse_mode="HTML"
        )

    elif data.startswith("graid_fight_"):
        raid_id = int(data.split("_")[-1])
        guild = db.get_user_guild(user_id)
        if not guild or guild['leader_id'] != user_id:
            await query.answer("Only the guild leader can start the fight!", show_alert=True)
            return
        await execute_guild_raid(update, context, raid_id, guild)


async def show_graid_char(update, context, index, chars, raid_id):
    query = update.callback_query
    char = chars[index]

    text = (
        f"🧬 <b>SELECT YOUR CHARACTER FOR GUILD RAID</b>\n\n"
        f"⚡ {char['name']}\n"
        f"💪 Power: {format_coins(char['power'])}\n"
        f"🔥 Skill: {char.get('skill', 'None')}\n\n"
        f"Character {index + 1} of {len(chars)}"
    )

    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"graid_char_prev_{index}"))
    if index < len(chars) - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"graid_char_next_{index}"))
    select_row = [InlineKeyboardButton("✅ Join with this character!", callback_data=f"graid_char_select_{raid_id}_{index}")]

    rows = []
    if nav_row:
        rows.append(nav_row)
    rows.append(select_row)
    buttons = InlineKeyboardMarkup(rows)

    try:
        if char.get('image_file_id'):
            await query.edit_message_media(
                media=InputMediaPhoto(media=char['image_file_id'], caption=text, parse_mode="HTML"),
                reply_markup=buttons
            )
        else:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)
    except Exception:
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)


async def execute_guild_raid(update, context, raid_id, guild):
    query = update.callback_query
    participants = db.get_guild_raid_participants(raid_id)

    if len(participants) < 1:
        await query.answer("Need at least 1 participant!", show_alert=True)
        return

    raid = db.get_active_guild_raid(guild['guild_id'])
    if not raid:
        await query.answer("Raid not found!")
        return

    total_power = sum(p['power'] for p in participants)
    boss_power = raid['boss_power']
    boss_health = raid['boss_health']
    boss_rewards = raid['boss_rewards']

    if total_power >= boss_power:
        db.set_guild_raid_status(raid_id, 'completed')
        leader_bonus = int(boss_rewards * 0.1)
        remaining_reward = boss_rewards
        per_member = remaining_reward // len(participants)

        db.add_coins(guild['leader_id'], leader_bonus)
        db.update_guild_points(guild['guild_id'], 100)

        for p in participants:
            db.add_coins(p['user_id'], per_member)
            db.add_xp_and_level(p['user_id'], per_member // 10)

        participant_text = ""
        for p in participants:
            name = f"@{p['username']}" if p['username'] else p.get('first_name', 'Unknown')
            participant_text += f"• {name} with {p['char_name']} (Power: {format_coins(p['power'])})\n"

        text = (
            f"🏆 <b>GUILD RAID VICTORY!</b>\n\n"
            f"🏰 Guild: <b>{guild['name']}</b>\n"
            f"🐉 Boss: <b>{raid['boss_name']}</b> DEFEATED!\n\n"
            f"💪 Total Power: {format_coins(total_power)} vs {format_coins(boss_power)}\n\n"
            f"<b>Participants:</b>\n{participant_text}\n"
            f"💰 Total Reward: {format_coins(boss_rewards)} coins\n"
            f"👑 Leader Bonus: {format_coins(leader_bonus)} coins\n"
            f"⚔️ Each Member: {format_coins(per_member)} coins\n"
            f"🏆 +100 Guild Points!"
        )
    else:
        db.set_guild_raid_status(raid_id, 'failed')
        for p in participants:
            db.set_character_dead(p['user_id'], p['char_id'], hours=3.0)

        text = (
            f"💀 <b>GUILD RAID FAILED!</b>\n\n"
            f"🐉 {raid['boss_name']} was too powerful!\n"
            f"💪 Team Power: {format_coins(total_power)} vs Boss: {format_coins(boss_power)}\n\n"
            f"All participating characters are dead for 3 hours!"
        )

    try:
        await query.edit_message_text(text, parse_mode="HTML")
    except Exception:
        await query.message.reply_text(text, parse_mode="HTML")


def get_handlers():
    return [
        CommandHandler("guildcreate", cmd_guild_create),
        CommandHandler("guildjoin", cmd_guild_join),
        CommandHandler("guildleave", cmd_guild_leave),
        CommandHandler("guildinfo", cmd_guild_info),
        CommandHandler("guildleaderboard", cmd_guild_leaderboard),
        CommandHandler("raidboss", cmd_raidboss),
        CallbackQueryHandler(guild_callback, pattern="^(guild_|graid_)"),
    ]
