import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import database as db
from utils.helpers import format_coins, format_time_remaining, is_character_dead, battlepass_active
from config import TOURNAMENT_MAX_PLAYERS, TOURNAMENT_DURATION_HOURS


async def cmd_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")

    t = db.get_ongoing_tournament()
    if not t:
        await update.message.reply_text(
            "🏆 No active tournaments!\n\n"
            "Ask an admin to create one via /admins",
        )
        return

    participants = db.get_tournament_participants(t['tournament_id'])
    count = len(participants)

    end_time = (t['start_time'] or time.time()) + TOURNAMENT_DURATION_HOURS * 3600
    time_left = format_time_remaining(end_time) if end_time > time.time() else "Starting soon..."

    text = (
        f"🏆 <b>TOURNAMENT #{t['tournament_id']}</b>\n\n"
        f"📊 Status: <b>{t['status']}</b>\n"
        f"👥 Players: {count}/{TOURNAMENT_MAX_PLAYERS}\n"
        f"⏳ Time Left: {time_left}\n\n"
        f"💰 Rewards:\n"
        f"   🥇 Winner: {format_coins(t['reward_coins'])} coins + {format_coins(t['reward_xp'])} XP\n\n"
        f"<b>Participants:</b>\n"
    )

    for p in participants[:10]:
        name = f"@{p['username']}" if p['username'] else p.get('first_name', 'Unknown')
        text += f"• {name} — {p['char_name']} (Power: {format_coins(p['power'])})\n"

    if count > 10:
        text += f"...and {count - 10} more"

    join_btn = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚔️ Join Tournament", callback_data=f"tournament_join_{t['tournament_id']}")
    ]])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=join_btn)


async def cmd_join_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        db.register_group(chat.id, chat.title or "Unknown Group")
    db.register_user(user.id, user.username or "", user.first_name or "")
    db.revive_dead_characters()

    t = db.get_open_tournament()
    if not t:
        await update.message.reply_text(
            "🏆 No open tournaments! Ask an admin to create one.",
        )
        return

    if db.is_in_tournament(t['tournament_id'], user.id):
        await update.message.reply_text("❌ You're already in this tournament!")
        return

    count = db.count_tournament_participants(t['tournament_id'])
    if count >= TOURNAMENT_MAX_PLAYERS:
        await update.message.reply_text("❌ Tournament is full!")
        return

    chars = db.get_user_characters(user.id)
    alive_chars = [c for c in chars if not is_character_dead(c)]

    if not alive_chars:
        await update.message.reply_text("❌ You have no alive characters!")
        return

    context.user_data['tournament_id'] = t['tournament_id']
    context.user_data['tournament_chars'] = alive_chars
    context.user_data['tournament_char_index'] = 0

    await update.message.reply_text(
        f"🏆 <b>JOIN TOURNAMENT #{t['tournament_id']}</b>\n\n"
        f"Select your champion character:",
        parse_mode="HTML"
    )
    await show_tournament_char(update, context, 0, is_callback=False)


async def show_tournament_char(update, context, index, is_callback=False):
    chars = context.user_data.get('tournament_chars', [])
    if not chars or index >= len(chars):
        return

    char = chars[index]
    text = (
        f"🏆 <b>CHOOSE YOUR CHAMPION</b>\n\n"
        f"🧬 <b>{char['name']}</b>\n"
        f"💪 Power: {format_coins(char['power'])}\n"
        f"🔥 Skill: {char.get('skill', 'None')}\n"
        f"💎 Rarity: {char.get('rarity', 'Common')}\n\n"
        f"Character {index + 1} of {len(chars)}"
    )

    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"trn_char_prev_{index}"))
    if index < len(chars) - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"trn_char_next_{index}"))

    select_row = [InlineKeyboardButton("🏆 Enter Tournament!", callback_data=f"trn_confirm_{index}")]
    rows = []
    if nav_row:
        rows.append(nav_row)
    rows.append(select_row)
    buttons = InlineKeyboardMarkup(rows)

    if is_callback:
        query = update.callback_query
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
    else:
        if char.get('image_file_id'):
            await update.message.reply_photo(photo=char['image_file_id'], caption=text,
                                              parse_mode="HTML", reply_markup=buttons)
        else:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)


async def tournament_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("tournament_join_"):
        t_id = int(data.split("_")[-1])
        await cmd_join_tournament(update, context)

    elif data.startswith("trn_char_prev_"):
        index = max(0, int(data.split("_")[-1]) - 1)
        context.user_data['tournament_char_index'] = index
        await show_tournament_char(update, context, index, is_callback=True)

    elif data.startswith("trn_char_next_"):
        chars = context.user_data.get('tournament_chars', [])
        index = min(len(chars) - 1, int(data.split("_")[-1]) + 1)
        context.user_data['tournament_char_index'] = index
        await show_tournament_char(update, context, index, is_callback=True)

    elif data.startswith("trn_confirm_"):
        index = int(data.split("_")[-1])
        chars = context.user_data.get('tournament_chars', [])
        t_id = context.user_data.get('tournament_id')

        if not chars or index >= len(chars) or not t_id:
            await query.answer("Session expired! Use /jointournament again.", show_alert=True)
            return

        char = chars[index]
        if is_character_dead(char):
            await query.answer("Character is dead!", show_alert=True)
            return

        if db.is_in_tournament(t_id, user_id):
            await query.answer("Already in tournament!", show_alert=True)
            return

        db.join_tournament(t_id, user_id, char['char_id'])
        count = db.count_tournament_participants(t_id)

        text = (
            f"🏆 <b>TOURNAMENT JOINED!</b>\n\n"
            f"🧬 Your Champion: <b>{char['name']}</b>\n"
            f"💪 Power: {format_coins(char['power'])}\n"
            f"👥 Players: {count}/{TOURNAMENT_MAX_PLAYERS}\n\n"
        )

        if count >= TOURNAMENT_MAX_PLAYERS:
            text += "🚀 Tournament is starting now!"
            db.set_tournament_ongoing(t_id)
            await query.edit_message_text(text, parse_mode="HTML")
            await resolve_tournament(context, t_id)
        else:
            text += f"⏳ Waiting for {TOURNAMENT_MAX_PLAYERS - count} more players..."
            await query.edit_message_text(text, parse_mode="HTML")


async def resolve_tournament(context, tournament_id: int):
    participants = db.get_tournament_participants(tournament_id)
    if not participants:
        return

    winner = max(participants, key=lambda p: p['power'])
    t = db.get_ongoing_tournament()
    if not t:
        return

    db.finish_tournament(tournament_id, winner['user_id'])
    db.add_coins(winner['user_id'], t['reward_coins'])
    db.add_xp_and_level(winner['user_id'], t['reward_xp'])

    winner_name = f"@{winner['username']}" if winner['username'] else winner.get('first_name', 'Unknown')

    result_text = (
        f"🏆 <b>TOURNAMENT RESULTS!</b>\n\n"
        f"🥇 <b>WINNER: {winner_name}</b>\n"
        f"🧬 Champion: {winner['char_name']}\n"
        f"💪 Power: {format_coins(winner['power'])}\n\n"
        f"💰 Prize: {format_coins(t['reward_coins'])} coins\n"
        f"📊 XP: +{format_coins(t['reward_xp'])}\n\n"
        f"Congratulations! 🎉"
    )

    for p in participants:
        try:
            await context.bot.send_message(
                chat_id=p['user_id'],
                text=result_text,
                parse_mode="HTML"
            )
        except Exception:
            pass


async def cmd_tournament_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏆 <b>TOURNAMENT LEADERBOARD</b>\n\nUse /leaderboard to see overall rankings.",
        parse_mode="HTML"
    )


def get_handlers():
    return [
        CommandHandler("tournament", cmd_tournament),
        CommandHandler("jointournament", cmd_join_tournament),
        CommandHandler("tournamentleaderboard", cmd_tournament_leaderboard),
        CallbackQueryHandler(tournament_callback, pattern="^(tournament_|trn_)"),
    ]
