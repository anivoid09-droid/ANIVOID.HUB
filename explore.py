import time
import random
from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import database as db
from utils.helpers import format_coins, format_time_remaining, is_character_dead, battlepass_active
from utils.buttons import map_selection_buttons, char_selection_buttons


async def cmd_explore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        db.register_group(chat.id, chat.title or "Unknown Group")
    db.register_user(user.id, user.username or "", user.first_name or "")
    db.revive_dead_characters()

    maps = db.get_all_maps()
    if not maps:
        await update.message.reply_text(
            "🗺️ No maps available yet. Ask an admin to add maps!",
        )
        return

    context.user_data['explore_maps'] = maps
    context.user_data['explore_map_index'] = 0
    await show_map(update, context, 0, is_callback=False)


async def show_map(update, context, index, is_callback=False):
    maps = context.user_data.get('explore_maps', [])
    if not maps or index >= len(maps):
        return

    m = maps[index]
    text = (
        f"🗺️ <b>MAP: {m['name']}</b>\n\n"
        f"👹 Boss Count: {m['boss_count']}\n"
        f"⚠️ Danger Level: {m['danger_level']}/10\n"
        f"💰 Reward: {format_coins(m['reward'])} coins\n\n"
        f"📍 Map {index + 1} of {len(maps)}"
    )

    buttons = map_selection_buttons(index, len(maps))

    if m.get('image_file_id'):
        if is_callback:
            query = update.callback_query
            try:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=m['image_file_id'], caption=text, parse_mode="HTML"),
                    reply_markup=buttons
                )
            except Exception:
                await query.message.reply_photo(photo=m['image_file_id'], caption=text,
                                                 parse_mode="HTML", reply_markup=buttons)
        else:
            await update.message.reply_photo(photo=m['image_file_id'], caption=text,
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


async def show_character_for_explore(update, context, index, is_callback=True):
    user_id = update.effective_user.id
    characters = context.user_data.get('explore_chars', [])
    if not characters or index >= len(characters):
        query = update.callback_query
        await query.answer("No more characters!")
        return

    char = characters[index]
    dead = is_character_dead(char)
    status_text = ""
    if dead:
        status_text = f"\n☠️ Dead — revives in {format_time_remaining(char['dead_until'])}"

    text = (
        f"🧬 <b>SELECT CHARACTER</b>\n\n"
        f"⚡ <b>{char['name']}</b>\n"
        f"💪 Power: {format_coins(char['power'])}\n"
        f"🔥 Skill: {char['skill'] or 'None'}\n"
        f"💎 Rarity: {char['rarity']}\n"
        f"❤️ Health: {char['current_health']}/100\n"
        f"📋 Status: {'☠️ Dead' if dead else '✅ Alive'}{status_text}\n\n"
        f"🧬 Character {index + 1} of {len(characters)}"
    )

    extra = []
    if not dead:
        extra = [[]]
        extra[0].append(__import__('telegram').InlineKeyboardButton(
            "✅ Choose This", callback_data=f"expl_confirm_{index}"))

    buttons = char_selection_buttons(index, len(characters), "expl_char")
    if not dead:
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        rows = []
        nav_row = []
        if index > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"expl_char_prev_{index}"))
        if index < len(characters) - 1:
            nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"expl_char_next_{index}"))
        if nav_row:
            rows.append(nav_row)
        rows.append([InlineKeyboardButton("✅ Explore with this character!", callback_data=f"expl_confirm_{index}")])
        buttons = InlineKeyboardMarkup(rows)

    query = update.callback_query
    if char.get('image_file_id'):
        try:
            await query.edit_message_media(
                media=InputMediaPhoto(media=char['image_file_id'], caption=text, parse_mode="HTML"),
                reply_markup=buttons
            )
        except Exception:
            await query.message.reply_photo(photo=char['image_file_id'], caption=text,
                                             parse_mode="HTML", reply_markup=buttons)
    else:
        try:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=buttons)
        except Exception:
            await query.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)


async def explore_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("map_prev_"):
        index = max(0, int(data.split("_")[-1]) - 1)
        context.user_data['explore_map_index'] = index
        await show_map(update, context, index, is_callback=True)

    elif data.startswith("map_next_"):
        maps = context.user_data.get('explore_maps', [])
        index = min(len(maps) - 1, int(data.split("_")[-1]) + 1)
        context.user_data['explore_map_index'] = index
        await show_map(update, context, index, is_callback=True)

    elif data.startswith("map_select_"):
        index = int(data.split("_")[-1])
        maps = context.user_data.get('explore_maps', [])
        if not maps or index >= len(maps):
            await query.answer("Invalid map!")
            return
        context.user_data['selected_map'] = maps[index]

        chars = db.get_user_characters(user_id)
        db.revive_dead_characters()
        chars = db.get_user_characters(user_id)

        if not chars:
            try:
                await query.edit_message_text(
                    "❌ You have no characters! Visit /market to buy some.",
                    parse_mode="HTML"
                )
            except Exception:
                await query.message.reply_text("❌ You have no characters! Visit /market to buy some.")
            return

        context.user_data['explore_chars'] = chars
        context.user_data['explore_char_index'] = 0
        await show_character_for_explore(update, context, 0)

    elif data.startswith("expl_char_prev_"):
        index = max(0, int(data.split("_")[-1]) - 1)
        context.user_data['explore_char_index'] = index
        await show_character_for_explore(update, context, index)

    elif data.startswith("expl_char_next_"):
        chars = context.user_data.get('explore_chars', [])
        index = min(len(chars) - 1, int(data.split("_")[-1]) + 1)
        context.user_data['explore_char_index'] = index
        await show_character_for_explore(update, context, index)

    elif data.startswith("expl_confirm_"):
        index = int(data.split("_")[-1])
        chars = context.user_data.get('explore_chars', [])
        sel_map = context.user_data.get('selected_map')

        if not chars or index >= len(chars) or not sel_map:
            await query.answer("Session expired. Use /explore again.")
            return

        char = chars[index]
        if is_character_dead(char):
            remaining = format_time_remaining(char['dead_until'])
            await query.answer(f"Character is dead! Revives in {remaining}", show_alert=True)
            return

        await run_exploration(update, context, char, sel_map)


async def run_exploration(update, context, char, sel_map):
    query = update.callback_query
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    bosses = db.get_bosses_by_type('explore_boss')
    if not bosses:
        bosses_to_fight = []
        for i in range(sel_map['boss_count']):
            bosses_to_fight.append({
                'name': f"Shadow Demon {i+1}",
                'power': (sel_map['danger_level'] * 200) + random.randint(-50, 50),
                'rewards': sel_map['reward'] // sel_map['boss_count']
            })
    else:
        danger = sel_map['danger_level']
        filtered = [b for b in bosses if b['power'] <= char['power'] * 3]
        if not filtered:
            filtered = bosses[:min(sel_map['boss_count'], len(bosses))]
        bosses_to_fight = random.choices(filtered, k=min(sel_map['boss_count'], len(filtered)))

    total_reward = 0
    total_xp = 0
    results = []
    died = False

    for boss in bosses_to_fight:
        if char['power'] >= boss['power']:
            reward = int(sel_map['reward'] / sel_map['boss_count'])
            if battlepass_active(user):
                reward = int(reward * 1.1)
            xp_gain = max(50, reward // 10)
            total_reward += reward
            total_xp += xp_gain
            results.append(f"✅ Defeated <b>{boss['name']}</b> (+{format_coins(reward)} coins)")
        else:
            results.append(f"☠️ <b>{char['name']}</b> was killed by <b>{boss['name']}</b>!")
            db.set_character_dead(user_id, char['char_id'], hours=3.0)
            died = True
            break

    if total_reward > 0:
        db.add_coins(user_id, total_reward)
        db.add_xp_and_level(user_id, total_xp)

    result_text = "\n".join(results)
    summary = ""
    if not died:
        summary = f"\n\n🎉 <b>Exploration Complete!</b>\n💰 Total Reward: {format_coins(total_reward)} coins\n📊 XP Gained: {total_xp}"
    else:
        summary = f"\n\n☠️ Your character died during exploration and will revive in 3 hours.\n💰 Partial reward: {format_coins(total_reward)} coins collected before death."

    text = (
        f"⚔️ <b>EXPLORING: {sel_map['name']}</b>\n\n"
        f"{result_text}{summary}"
    )

    try:
        await query.edit_message_text(text=text, parse_mode="HTML")
    except Exception:
        await query.message.reply_text(text, parse_mode="HTML")


async def cmd_adventure(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_explore(update, context)


def get_handlers():
    return [
        CommandHandler("explore", cmd_explore),
        CommandHandler("adventure", cmd_adventure),
        CallbackQueryHandler(explore_callback, pattern="^(map_|expl_)"),
    ]
