import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import database as db
from utils.helpers import format_coins, is_character_dead, get_skill_power, get_display_name


PENDING_FIGHTS = {}


async def cmd_cardfight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        db.register_group(chat.id, chat.title or "Unknown Group")
    db.register_user(user.id, user.username or "", user.first_name or "")

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚔️ Reply to a player's message with /cardfight to challenge them!"
        )
        return

    opponent = update.message.reply_to_message.from_user
    if opponent.id == user.id:
        await update.message.reply_text("❌ You can't fight yourself!")
        return
    if opponent.is_bot:
        await update.message.reply_text("❌ You can't fight a bot!")
        return

    db.register_user(opponent.id, opponent.username or "", opponent.first_name or "")

    initiator_cards = db.get_user_cards(user.id)
    if not initiator_cards:
        await update.message.reply_text("❌ You have no cards! Visit /market to buy some.")
        return

    opp_cards = db.get_user_cards(opponent.id)
    if not opp_cards:
        await update.message.reply_text(
            f"❌ {get_display_name(opponent)} has no cards!"
        )
        return

    fight_id = f"{user.id}_{opponent.id}_{int(time.time())}"
    PENDING_FIGHTS[fight_id] = {
        'initiator_id': user.id,
        'opponent_id': opponent.id,
        'initiator_card': None,
        'opponent_card': None,
        'chat_id': update.effective_chat.id,
    }

    context.user_data['card_fight_id'] = fight_id
    context.user_data['cf_cards'] = initiator_cards
    context.user_data['cf_index'] = 0

    opp_name = get_display_name(opponent)
    await update.message.reply_text(
        f"⚔️ <b>CARD FIGHT INITIATED!</b>\n\n"
        f"🎯 <b>{get_display_name(user)}</b> vs <b>{opp_name}</b>\n\n"
        f"<b>{get_display_name(user)}</b>, select your card:",
        parse_mode="HTML"
    )

    await show_card_for_fight(update, context, 0, initiator_cards, fight_id, "initiator", is_callback=False)


async def show_card_for_fight(update_or_query, context, index, cards, fight_id, role, is_callback=False):
    if not cards or index >= len(cards):
        return

    card = cards[index]
    skill_power = get_skill_power(card.get('skill', ''))
    total_power = card['power'] + skill_power

    text = (
        f"🃏 <b>YOUR CARDS</b>\n\n"
        f"🎴 <b>{card['name']}</b>\n"
        f"💪 Power: {format_coins(card['power'])}\n"
        f"🔥 Skill: {card.get('skill', 'None')} (+{skill_power})\n"
        f"⚡ Total: {format_coins(total_power)}\n"
        f"💎 Rarity: {card.get('rarity', 'Common')}\n\n"
        f"Card {index + 1} of {len(cards)}"
    )

    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"cf_{role}_prev_{fight_id}_{index}"))
    if index < len(cards) - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"cf_{role}_next_{fight_id}_{index}"))

    select_row = [InlineKeyboardButton("⚔️ Fight with this card!", callback_data=f"cf_{role}_select_{fight_id}_{index}")]

    rows = []
    if nav_row:
        rows.append(nav_row)
    rows.append(select_row)
    buttons = InlineKeyboardMarkup(rows)

    if is_callback:
        query = update_or_query.callback_query
        try:
            if card.get('image_file_id'):
                await query.edit_message_media(
                    media=InputMediaPhoto(media=card['image_file_id'], caption=text, parse_mode="HTML"),
                    reply_markup=buttons
                )
            else:
                await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)
        except Exception:
            if card.get('image_file_id'):
                await query.message.reply_photo(photo=card['image_file_id'], caption=text,
                                                  parse_mode="HTML", reply_markup=buttons)
            else:
                await query.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)
    else:
        msg = update_or_query.message
        if card.get('image_file_id'):
            await msg.reply_photo(photo=card['image_file_id'], caption=text,
                                   parse_mode="HTML", reply_markup=buttons)
        else:
            await msg.reply_text(text, parse_mode="HTML", reply_markup=buttons)


async def cardfight_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    parts = data.split("_")
    role = parts[1]
    action = parts[2]

    fight_id = "_".join(parts[3:-1])
    index = int(parts[-1])

    fight = PENDING_FIGHTS.get(fight_id)
    if not fight:
        await query.answer("Fight session expired!", show_alert=True)
        return

    if role == "initiator" and user_id != fight['initiator_id']:
        await query.answer("This isn't your card selection!", show_alert=True)
        return
    if role == "opponent" and user_id != fight['opponent_id']:
        await query.answer("This isn't your card selection!", show_alert=True)
        return

    if role == "initiator":
        cards = db.get_user_cards(fight['initiator_id'])
    else:
        cards = db.get_user_cards(fight['opponent_id'])

    if action == "prev":
        new_index = max(0, index - 1)
        await show_card_for_fight(update, context, new_index, cards, fight_id, role, is_callback=True)
    elif action == "next":
        new_index = min(len(cards) - 1, index + 1)
        await show_card_for_fight(update, context, new_index, cards, fight_id, role, is_callback=True)
    elif action == "select":
        selected_card = cards[index]
        if role == "initiator":
            fight['initiator_card'] = selected_card
            await query.edit_message_text(
                f"✅ You selected <b>{selected_card['name']}</b>!\n\nWaiting for opponent...",
                parse_mode="HTML"
            )
            opp_cards = db.get_user_cards(fight['opponent_id'])
            opp_user = await context.bot.get_chat(fight['opponent_id'])
            opp_name = f"@{opp_user.username}" if opp_user.username else opp_user.first_name

            opp_text = (
                f"⚔️ <b>CARD FIGHT CHALLENGE!</b>\n\n"
                f"You've been challenged to a card fight!\n"
                f"Select your card to fight:"
            )

            await context.bot.send_message(
                chat_id=fight['opponent_id'],
                text=opp_text,
                parse_mode="HTML"
            )

            await show_card_for_fight_to_user(context, fight['opponent_id'], 0, opp_cards, fight_id, "opponent")

        elif role == "opponent":
            fight['opponent_card'] = selected_card
            await query.edit_message_text(
                f"✅ You selected <b>{selected_card['name']}</b>!\n\nResolving fight...",
                parse_mode="HTML"
            )
            await resolve_fight(context, fight_id, fight)


async def show_card_for_fight_to_user(context, chat_id, index, cards, fight_id, role):
    if not cards:
        await context.bot.send_message(chat_id=chat_id, text="❌ You have no cards!")
        return

    card = cards[index]
    skill_power = get_skill_power(card.get('skill', ''))
    total_power = card['power'] + skill_power

    text = (
        f"🃏 <b>SELECT YOUR CARD</b>\n\n"
        f"🎴 <b>{card['name']}</b>\n"
        f"💪 Power: {format_coins(card['power'])}\n"
        f"🔥 Skill: {card.get('skill', 'None')} (+{skill_power})\n"
        f"⚡ Total: {format_coins(total_power)}\n"
        f"💎 Rarity: {card.get('rarity', 'Common')}\n\n"
        f"Card {index + 1} of {len(cards)}"
    )

    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"cf_{role}_prev_{fight_id}_{index}"))
    if index < len(cards) - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"cf_{role}_next_{fight_id}_{index}"))
    select_row = [InlineKeyboardButton("⚔️ Fight with this card!", callback_data=f"cf_{role}_select_{fight_id}_{index}")]

    rows = []
    if nav_row:
        rows.append(nav_row)
    rows.append(select_row)
    buttons = InlineKeyboardMarkup(rows)

    if card.get('image_file_id'):
        await context.bot.send_photo(chat_id=chat_id, photo=card['image_file_id'],
                                      caption=text, parse_mode="HTML", reply_markup=buttons)
    else:
        await context.bot.send_message(chat_id=chat_id, text=text,
                                        parse_mode="HTML", reply_markup=buttons)


async def resolve_fight(context, fight_id, fight):
    init_card = fight.get('initiator_card')
    opp_card = fight.get('opponent_card')

    if not init_card or not opp_card:
        return

    init_power = init_card['power'] + get_skill_power(init_card.get('skill', ''))
    opp_power = opp_card['power'] + get_skill_power(opp_card.get('skill', ''))

    init_user = await context.bot.get_chat(fight['initiator_id'])
    opp_user = await context.bot.get_chat(fight['opponent_id'])
    init_name = f"@{init_user.username}" if init_user.username else init_user.first_name
    opp_name = f"@{opp_user.username}" if opp_user.username else opp_user.first_name

    REWARD = 10000

    if init_power > opp_power:
        winner_id = fight['initiator_id']
        loser_id = fight['opponent_id']
        winner_name = init_name
        winner_card = init_card
        loser_card = opp_card
    elif opp_power > init_power:
        winner_id = fight['opponent_id']
        loser_id = fight['initiator_id']
        winner_name = opp_name
        winner_card = opp_card
        loser_card = init_card
    else:
        result_text = (
            f"🤝 <b>CARD FIGHT RESULT: TIE!</b>\n\n"
            f"⚔️ {init_name} vs {opp_name}\n"
            f"🃏 {init_card['name']} ({format_coins(init_power)}) vs {opp_card['name']} ({format_coins(opp_power)})\n\n"
            f"Both cards had equal power! No reward."
        )
        await context.bot.send_message(chat_id=fight['chat_id'], text=result_text, parse_mode="HTML")
        await context.bot.send_message(chat_id=fight['initiator_id'], text="🤝 Card fight ended in a tie!")
        await context.bot.send_message(chat_id=fight['opponent_id'], text="🤝 Card fight ended in a tie!")
        PENDING_FIGHTS.pop(fight_id, None)
        return

    db.add_coins(winner_id, REWARD)
    db.add_xp_and_level(winner_id, 500)

    result_text = (
        f"🏆 <b>CARD FIGHT RESULT!</b>\n\n"
        f"⚔️ {init_name} vs {opp_name}\n\n"
        f"🃏 {init_name}: <b>{init_card['name']}</b> (Power: {format_coins(init_power)})\n"
        f"🃏 {opp_name}: <b>{opp_card['name']}</b> (Power: {format_coins(opp_power)})\n\n"
        f"🏆 <b>WINNER: {winner_name}!</b>\n"
        f"💰 Prize: {format_coins(REWARD)} coins awarded!"
    )

    await context.bot.send_message(chat_id=fight['chat_id'], text=result_text, parse_mode="HTML")
    await context.bot.send_message(chat_id=winner_id, text=f"🏆 You won the card fight! +{format_coins(REWARD)} coins!")
    await context.bot.send_message(chat_id=loser_id, text="💀 You lost the card fight! Better luck next time.")

    PENDING_FIGHTS.pop(fight_id, None)


def get_handlers():
    return [
        CommandHandler("cardfight", cmd_cardfight),
        CallbackQueryHandler(cardfight_callback, pattern="^cf_"),
    ]
