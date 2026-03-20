import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import database as db
from utils.helpers import (format_coins, format_time_remaining, is_character_dead,
                            calculate_raid_duration, battlepass_active)


async def cmd_raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        db.register_group(chat.id, chat.title or "Unknown Group")
    db.register_user(user.id, user.username or "", user.first_name or "")
    db.revive_dead_characters()

    active = db.get_active_raid(user.id)
    if active:
        if active['end_time'] > time.time():
            remaining = format_time_remaining(active['end_time'])
            await update.message.reply_text(
                f"⚔️ You're already in a raid!\n"
                f"🐉 Boss: {active['boss_name']}\n"
                f"⏳ Ends in: {remaining}\n\n"
                f"Use /damage to check your progress.",
                parse_mode="HTML"
            )
            return

    raid_bosses = db.get_all_raid_bosses()
    if not raid_bosses:
        await update.message.reply_text(
            "🐉 No raid bosses available! Ask an admin to add some.",
        )
        return

    boss = raid_bosses[0]
    context.user_data['raid_boss'] = boss

    chars = db.get_user_characters(user.id)
    if not chars:
        await update.message.reply_text("❌ You have no characters! Visit /market to get some.")
        return

    context.user_data['raid_chars'] = chars
    context.user_data['raid_char_index'] = 0

    await show_raid_character(update, context, 0, is_callback=False)


async def show_raid_character(update, context, index, is_callback=False):
    chars = context.user_data.get('raid_chars', [])
    boss = context.user_data.get('raid_boss', {})

    if not chars or index >= len(chars):
        return

    char = chars[index]
    dead = is_character_dead(char)
    power_check = char['power'] >= boss.get('power', 0) * 0.5
    status = "☠️ Dead" if dead else ("✅ Strong enough" if power_check else "⚠️ Too weak (50% boss power)")

    text = (
        f"🐉 <b>RAID BOSS: {boss.get('name', 'Unknown')}</b>\n"
        f"💪 Boss Power: {format_coins(boss.get('power', 0))}\n"
        f"💰 Reward: {format_coins(boss.get('rewards', 0))} coins\n\n"
        f"🧬 <b>SELECT CHARACTER</b>\n"
        f"⚡ {char['name']}\n"
        f"💪 Power: {format_coins(char['power'])}\n"
        f"📋 Status: {status}\n\n"
        f"Character {index + 1} of {len(chars)}"
    )

    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"raid_char_prev_{index}"))
    if index < len(chars) - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"raid_char_next_{index}"))

    rows = []
    if nav_row:
        rows.append(nav_row)
    if not dead:
        rows.append([InlineKeyboardButton("⚔️ Start Raid!", callback_data=f"raid_confirm_{index}")])

    buttons = InlineKeyboardMarkup(rows)

    if char.get('image_file_id'):
        if is_callback:
            query = update.callback_query
            try:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=char['image_file_id'], caption=text, parse_mode="HTML"),
                    reply_markup=buttons
                )
            except Exception:
                await query.message.reply_photo(photo=char['image_file_id'], caption=text,
                                                 parse_mode="HTML", reply_markup=buttons)
        else:
            await update.message.reply_photo(photo=char['image_file_id'], caption=text,
                                              parse_mode="HTML", reply_markup=buttons)
    else:
        if is_callback:
            query = update.callback_query
            try:
                await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=buttons)
            except Exception:
                await query.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)
        else:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)


async def raid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("raid_char_prev_"):
        index = max(0, int(data.split("_")[-1]) - 1)
        context.user_data['raid_char_index'] = index
        await show_raid_character(update, context, index, is_callback=True)

    elif data.startswith("raid_char_next_"):
        chars = context.user_data.get('raid_chars', [])
        index = min(len(chars) - 1, int(data.split("_")[-1]) + 1)
        context.user_data['raid_char_index'] = index
        await show_raid_character(update, context, index, is_callback=True)

    elif data.startswith("raid_confirm_"):
        index = int(data.split("_")[-1])
        chars = context.user_data.get('raid_chars', [])
        boss = context.user_data.get('raid_boss')

        if not chars or index >= len(chars) or not boss:
            await query.answer("Session expired. Use /raid again.", show_alert=True)
            return

        char = chars[index]
        if is_character_dead(char):
            await query.answer("This character is dead!", show_alert=True)
            return

        if char['power'] < boss['power'] * 0.5:
            db.set_character_dead(user_id, char['char_id'], hours=3.0)
            text = (
                f"💀 <b>RAID FAILED!</b>\n\n"
                f"Your character <b>{char['name']}</b> was too weak!\n"
                f"⚔️ Your Power: {format_coins(char['power'])}\n"
                f"🐉 Boss Power: {format_coins(boss['power'])}\n\n"
                f"☠️ {char['name']} is dead for 3 hours!"
            )
            try:
                await query.edit_message_text(text, parse_mode="HTML")
            except Exception:
                await query.message.reply_text(text, parse_mode="HTML")
            return

        duration = calculate_raid_duration(char['power'], boss['power'])
        raid_id = db.create_active_raid(user_id, boss['id'], char['char_id'], duration)
        end_time = time.time() + duration

        minutes = duration // 60
        seconds = duration % 60

        user_data = db.get_user(user_id)
        reward = boss['rewards']
        if battlepass_active(user_data):
            reward = int(reward * 1.1)

        text = (
            f"⚔️ <b>RAID STARTED!</b>\n\n"
            f"🐉 Boss: <b>{boss['name']}</b>\n"
            f"🧬 Character: <b>{char['name']}</b>\n"
            f"💪 Your Power: {format_coins(char['power'])}\n"
            f"⏱️ Fight Duration: {minutes}m {seconds}s\n"
            f"💰 Expected Reward: {format_coins(reward)} coins\n\n"
            f"⏳ Raid ends at: {format_time_remaining(end_time)}\n"
            f"Use /damage to check progress!"
        )

        rows = [[InlineKeyboardButton("📊 Check Damage", callback_data=f"raid_damage_{raid_id}")]]
        buttons = InlineKeyboardMarkup(rows)

        try:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)
        except Exception:
            await query.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)

        asyncio.create_task(finalize_raid(update, context, raid_id, user_id, boss, char, reward, duration))

    elif data.startswith("raid_damage_"):
        raid_id = int(data.split("_")[-1])
        await query.answer("Check /damage for full info!")

    elif data == "raid_next":
        context.user_data.pop('raid_boss', None)
        context.user_data.pop('raid_chars', None)
        raid_bosses = db.get_all_raid_bosses()
        if not raid_bosses:
            await query.answer("No raid bosses available!")
            return
        boss = raid_bosses[0]
        context.user_data['raid_boss'] = boss
        chars = db.get_user_characters(update.effective_user.id)
        if not chars:
            await query.answer("No characters!")
            return
        context.user_data['raid_chars'] = chars
        context.user_data['raid_char_index'] = 0
        await show_raid_character(update, context, 0, is_callback=True)


async def finalize_raid(update, context, raid_id, user_id, boss, char, reward, duration):
    await asyncio.sleep(duration)
    try:
        raid = db.get_active_raid(user_id)
        if not raid or raid['status'] != 'active':
            return

        db.complete_raid(raid_id, won=True)
        db.add_coins(user_id, reward)
        db.add_xp_and_level(user_id, reward // 10)

        text = (
            f"🏆 <b>RAID VICTORY!</b>\n\n"
            f"🐉 You defeated <b>{boss['name']}</b>!\n"
            f"🧬 {char['name']} fought bravely!\n"
            f"💰 Reward: +{format_coins(reward)} coins\n"
            f"📊 XP: +{reward // 10}\n\n"
            f"Ready for another raid?"
        )

        next_btn = InlineKeyboardMarkup([[
            InlineKeyboardButton("⚔️ Next Raid", callback_data="raid_next")
        ]])

        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            reply_markup=next_btn
        )
    except Exception as e:
        print(f"Raid finalization error: {e}")


async def cmd_damage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")

    raid = db.get_active_raid(user.id)
    if not raid:
        await update.message.reply_text("❌ You're not in an active raid! Use /raid to start one.")
        return

    now = time.time()
    if raid['end_time'] <= now:
        text = "✅ Raid complete! You should have received your reward."
    else:
        elapsed = now - raid['start_time']
        total = raid['end_time'] - raid['start_time']
        progress = min(100, int((elapsed / total) * 100)) if total > 0 else 100
        remaining = format_time_remaining(raid['end_time'])

        text = (
            f"⚔️ <b>RAID STATUS</b>\n\n"
            f"🐉 Boss: <b>{raid['boss_name']}</b>\n"
            f"📊 Progress: {progress}%\n"
            f"⏳ Time Remaining: {remaining}\n"
            f"💰 Expected Reward: {format_coins(raid['boss_rewards'])} coins"
        )

    await update.message.reply_text(text, parse_mode="HTML")


def get_handlers():
    return [
        CommandHandler("raid", cmd_raid),
        CommandHandler("damage", cmd_damage),
        CallbackQueryHandler(raid_callback, pattern="^raid_"),
    ]
