import time
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import database as db
from utils.helpers import format_coins, format_time_remaining, battlepass_active, get_display_name
from config import LOOTBOX_PRICES, BATTLEPASS_PRICES


# ===== BANK COMMANDS =====

async def cmd_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")
    data = db.get_user(user.id)

    text = (
        f"🏦 <b>BANK</b>\n\n"
        f"💰 Wallet: {format_coins(data['coins'])} coins\n"
        f"🏦 Bank: {format_coins(data['bank'])} coins\n"
        f"💎 Total: {format_coins(data['coins'] + data['bank'])} coins\n\n"
        f"Commands:\n"
        f"/deposit &lt;amount&gt; — deposit to bank\n"
        f"/withdraw &lt;amount&gt; — withdraw from bank\n\n"
        f"🔒 Bank money cannot be robbed!"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")

    if not context.args:
        await update.message.reply_text("Usage: /deposit &lt;amount&gt;\nExample: /deposit 5000", parse_mode="HTML")
        return

    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount!")
        return

    if amount <= 0:
        await update.message.reply_text("❌ Amount must be positive!")
        return

    data = db.get_user(user.id)
    if data['coins'] < amount:
        await update.message.reply_text(
            f"❌ Not enough coins!\nWallet: {format_coins(data['coins'])} coins"
        )
        return

    conn = db.get_conn()
    conn.execute("UPDATE users SET coins = coins - ?, bank = bank + ? WHERE user_id = ?",
                 (amount, amount, user.id))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Deposited {format_coins(amount)} coins to bank!\n"
        f"🏦 Bank: {format_coins(data['bank'] + amount)} coins",
        parse_mode="HTML"
    )


async def cmd_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")

    if not context.args:
        await update.message.reply_text("Usage: /withdraw &lt;amount&gt;\nExample: /withdraw 5000", parse_mode="HTML")
        return

    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount!")
        return

    if amount <= 0:
        await update.message.reply_text("❌ Amount must be positive!")
        return

    data = db.get_user(user.id)
    if data['bank'] < amount:
        await update.message.reply_text(
            f"❌ Not enough in bank!\nBank: {format_coins(data['bank'])} coins"
        )
        return

    conn = db.get_conn()
    conn.execute("UPDATE users SET bank = bank - ?, coins = coins + ? WHERE user_id = ?",
                 (amount, amount, user.id))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Withdrew {format_coins(amount)} coins!\n"
        f"💰 Wallet: {format_coins(data['coins'] + amount)} coins"
    )


# ===== MINI GAMES =====

async def cmd_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")
    data = db.get_user(user.id)

    bet = 500
    if data['coins'] < bet:
        await update.message.reply_text(f"❌ You need at least {format_coins(bet)} coins to play dice!")
        return

    roll1 = random.randint(1, 6)
    roll2 = random.randint(1, 6)

    if roll1 > roll2:
        winnings = bet
        db.add_coins(user.id, winnings)
        result = f"🎲 You rolled {roll1} vs Bot {roll2}\n🏆 You WIN! +{format_coins(winnings)} coins!"
    elif roll2 > roll1:
        db.add_coins(user.id, -bet)
        result = f"🎲 You rolled {roll1} vs Bot {roll2}\n💀 You LOSE! -{format_coins(bet)} coins!"
    else:
        result = f"🎲 You rolled {roll1} vs Bot {roll2}\n🤝 TIE! No coins lost."

    await update.message.reply_text(f"🎲 <b>DICE GAME</b>\n\n{result}", parse_mode="HTML")


async def cmd_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")

    if not context.args:
        await update.message.reply_text("Usage: /bet &lt;amount&gt;\nExample: /bet 1000", parse_mode="HTML")
        return

    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount!")
        return

    if amount <= 0:
        await update.message.reply_text("❌ Bet must be positive!")
        return

    data = db.get_user(user.id)
    if data['coins'] < amount:
        await update.message.reply_text(f"❌ Not enough coins! You have {format_coins(data['coins'])} coins")
        return

    win = random.random() < 0.45

    if win:
        db.add_coins(user.id, amount)
        result = f"🏆 You WIN! +{format_coins(amount)} coins!"
    else:
        db.add_coins(user.id, -amount)
        result = f"💀 You LOSE! -{format_coins(amount)} coins!"

    await update.message.reply_text(
        f"🎰 <b>BET</b>\n\nAmount: {format_coins(amount)} coins\n{result}",
        parse_mode="HTML"
    )


async def cmd_rob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        db.register_group(chat.id, chat.title or "Unknown Group")
    db.register_user(user.id, user.username or "", user.first_name or "")

    if not update.message.reply_to_message:
        await update.message.reply_text("💰 Reply to someone's message with /rob to rob them!")
        return

    target = update.message.reply_to_message.from_user
    if target.id == user.id:
        await update.message.reply_text("❌ You can't rob yourself!")
        return
    if target.is_bot:
        await update.message.reply_text("❌ You can't rob a bot!")
        return

    db.register_user(target.id, target.username or "", target.first_name or "")
    attacker = db.get_user(user.id)
    victim = db.get_user(target.id)

    if victim['coins'] <= 0:
        await update.message.reply_text(f"❌ {get_display_name(target)} has no coins to rob!")
        return

    success = random.random() < 0.4

    if success:
        rob_amount = random.randint(1, min(victim['coins'], 5000))
        db.add_coins(target.id, -rob_amount)
        db.add_coins(user.id, rob_amount)
        await update.message.reply_text(
            f"🕵️ <b>ROBBERY SUCCESS!</b>\n\n"
            f"You robbed {get_display_name(target)} of {format_coins(rob_amount)} coins!\n"
            f"🔒 Note: Bank money is safe from robbery!",
            parse_mode="HTML"
        )
    else:
        fine = min(attacker['coins'], random.randint(200, 1000))
        db.add_coins(user.id, -fine)
        await update.message.reply_text(
            f"🚔 <b>ROBBERY FAILED!</b>\n\n"
            f"You got caught! Paid {format_coins(fine)} coins as fine!",
            parse_mode="HTML"
        )


async def cmd_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")
    data = db.get_user(user.id)

    bet = 300
    if data['coins'] < bet:
        await update.message.reply_text(f"❌ You need at least {format_coins(bet)} coins for slots!")
        return

    symbols = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]
    s1, s2, s3 = random.choices(symbols, k=3)

    if s1 == s2 == s3:
        mult = 10 if s3 == "7️⃣" else 5 if s3 == "💎" else 3
        winnings = bet * mult
        db.add_coins(user.id, winnings)
        result = f"🎉 JACKPOT! {s1}{s2}{s3} — +{format_coins(winnings)} coins!"
    elif s1 == s2 or s2 == s3 or s1 == s3:
        winnings = bet
        db.add_coins(user.id, winnings)
        result = f"✅ Two match! {s1}{s2}{s3} — +{format_coins(winnings)} coins!"
    else:
        db.add_coins(user.id, -bet)
        result = f"❌ No match! {s1}{s2}{s3} — -{format_coins(bet)} coins!"

    await update.message.reply_text(
        f"🎰 <b>SLOT MACHINE</b>\n\n[ {s1} | {s2} | {s3} ]\n\n{result}",
        parse_mode="HTML"
    )


async def cmd_flip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")
    data = db.get_user(user.id)

    if not context.args:
        await update.message.reply_text("Usage: /flip &lt;heads/tails&gt; &lt;amount&gt;\nExample: /flip heads 500", parse_mode="HTML")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /flip &lt;heads/tails&gt; &lt;amount&gt;", parse_mode="HTML")
        return

    choice = context.args[0].lower()
    if choice not in ("heads", "tails", "h", "t"):
        await update.message.reply_text("❌ Choose 'heads' or 'tails'!")
        return

    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount!")
        return

    if amount <= 0:
        await update.message.reply_text("❌ Amount must be positive!")
        return

    if data['coins'] < amount:
        await update.message.reply_text(f"❌ Not enough coins!")
        return

    result = random.choice(["heads", "tails"])
    user_choice = "heads" if choice in ("h", "heads") else "tails"
    emoji = "🪙"

    if result == user_choice:
        db.add_coins(user.id, amount)
        outcome = f"✅ {result.upper()}! You win +{format_coins(amount)} coins!"
    else:
        db.add_coins(user.id, -amount)
        outcome = f"❌ {result.upper()}! You lose -{format_coins(amount)} coins!"

    await update.message.reply_text(
        f"{emoji} <b>COIN FLIP</b>\n\nYou chose: {user_choice}\nResult: {result}\n\n{outcome}",
        parse_mode="HTML"
    )


# ===== MARKET =====

async def cmd_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        db.register_group(chat.id, chat.title or "Unknown Group")
    db.register_user(user.id, user.username or "", user.first_name or "")

    items = db.get_market_items()
    if not items:
        await update.message.reply_text(
            "🛒 <b>MARKET</b>\n\nNo items available yet! Ask an admin to add characters and cards.",
            parse_mode="HTML"
        )
        return

    context.user_data['market_items'] = items
    context.user_data['market_index'] = 0
    await show_market_item(update, context, 0, is_callback=False)


async def show_market_item(update, context, index, is_callback=False):
    items = context.user_data.get('market_items', [])
    if not items or index >= len(items):
        return

    item = items[index]
    user_id = update.effective_user.id

    from utils.helpers import rarity_emoji
    type_emoji = "🧬" if item['type'] == 'character' else "🃏"
    rarity = item.get('rarity', 'Common')

    text = (
        f"🛒 <b>MARKET</b> ({index + 1}/{len(items)})\n\n"
        f"{type_emoji} <b>{item['name']}</b> [{rarity_emoji(rarity)} {rarity}]\n"
        f"📦 Type: {item['type'].title()}\n"
        f"💪 Power: {format_coins(item['power'] or 0)}\n"
        f"🔥 Skill: {item.get('skill', 'None')}\n"
        f"💰 Price: {format_coins(item['price'])} coins\n"
    )

    if item.get('description'):
        text += f"📖 {item['description']}\n"

    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"mkt_prev_{index}"))
    if index < len(items) - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"mkt_next_{index}"))

    buy_row = [InlineKeyboardButton(f"🛒 Buy — {format_coins(item['price'])} coins",
                                     callback_data=f"mkt_buy_{item['type']}_{item['item_id']}_{index}")]
    rows = []
    if nav_row:
        rows.append(nav_row)
    rows.append(buy_row)
    buttons = InlineKeyboardMarkup(rows)

    if item.get('image_file_id'):
        if is_callback:
            query = update.callback_query
            try:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=item['image_file_id'], caption=text, parse_mode="HTML"),
                    reply_markup=buttons
                )
            except Exception:
                await query.message.reply_photo(photo=item['image_file_id'], caption=text,
                                                  parse_mode="HTML", reply_markup=buttons)
        else:
            await update.message.reply_photo(photo=item['image_file_id'], caption=text,
                                              parse_mode="HTML", reply_markup=buttons)
    else:
        if is_callback:
            query = update.callback_query
            try:
                await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)
            except Exception:
                await query.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)
        else:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)


async def market_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("mkt_prev_"):
        index = max(0, int(data.split("_")[-1]) - 1)
        context.user_data['market_index'] = index
        await show_market_item(update, context, index, is_callback=True)

    elif data.startswith("mkt_next_"):
        items = context.user_data.get('market_items', [])
        index = min(len(items) - 1, int(data.split("_")[-1]) + 1)
        context.user_data['market_index'] = index
        await show_market_item(update, context, index, is_callback=True)

    elif data.startswith("mkt_buy_"):
        parts = data.split("_")
        item_type = parts[2]
        item_id = int(parts[3])
        current_index = int(parts[4]) if len(parts) > 4 else 0

        items = context.user_data.get('market_items', [])
        item = next((i for i in items if i['type'] == item_type and i['item_id'] == item_id), None)
        if not item:
            await query.answer("Item not found!", show_alert=True)
            return

        if item_type == 'character' and db.user_owns_character(user_id, item_id):
            await query.answer("You already own this character!", show_alert=True)
            return
        if item_type == 'card' and db.user_owns_card(user_id, item_id):
            await query.answer("You already own this card!", show_alert=True)
            return

        if not db.deduct_coins(user_id, item['price']):
            await query.answer(f"Not enough coins! Price: {format_coins(item['price'])} coins", show_alert=True)
            return

        if item_type == 'character':
            db.give_character_to_user(user_id, item_id)
        else:
            db.give_card_to_user(user_id, item_id)

        await query.answer(f"✅ Purchased {item['name']}!", show_alert=True)
        try:
            items = db.get_market_items()
            context.user_data['market_items'] = items
            await show_market_item(update, context, min(current_index, len(items) - 1), is_callback=True)
        except Exception:
            pass


# ===== INVENTORY =====

async def cmd_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")
    db.revive_dead_characters()

    chars = db.get_user_characters(user.id)
    if not chars:
        await update.message.reply_text(
            "🧬 <b>YOUR CHARACTERS</b>\n\nNo characters yet! Visit /market to buy some.",
            parse_mode="HTML"
        )
        return

    context.user_data['inv_chars'] = chars
    context.user_data['inv_index'] = 0
    await show_inventory_char(update, context, 0, is_callback=False)


async def show_inventory_char(update, context, index, is_callback=False):
    chars = context.user_data.get('inv_chars', [])
    if not chars or index >= len(chars):
        return

    from utils.helpers import is_character_dead, format_time_remaining, rarity_emoji
    char = chars[index]
    dead = is_character_dead(char)
    status = f"☠️ Dead — revives in {format_time_remaining(char['dead_until'])}" if dead else "✅ Alive"

    text = (
        f"🧬 <b>YOUR CHARACTERS</b> ({index + 1}/{len(chars)})\n\n"
        f"{rarity_emoji(char.get('rarity', 'Common'))} <b>{char['name']}</b>\n"
        f"💪 Power: {format_coins(char['power'])}\n"
        f"🔥 Skill: {char.get('skill', 'None')}\n"
        f"❤️ Health: {char['current_health']}/100\n"
        f"💎 Rarity: {char.get('rarity', 'Common')}\n"
        f"📋 Status: {status}\n"
    )
    if char.get('description'):
        text += f"📖 {char['description']}\n"

    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"inv_prev_{index}"))
    if index < len(chars) - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"inv_next_{index}"))
    rows = [nav_row] if nav_row else []
    buttons = InlineKeyboardMarkup(rows) if rows else None

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


async def cmd_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")

    cards = db.get_user_cards(user.id)
    if not cards:
        await update.message.reply_text(
            "🃏 <b>YOUR CARDS</b>\n\nNo cards yet! Visit /market to buy some.",
            parse_mode="HTML"
        )
        return

    context.user_data['cards_list'] = cards
    context.user_data['cards_index'] = 0
    await show_user_card(update, context, 0, is_callback=False)


async def show_user_card(update, context, index, is_callback=False):
    cards = context.user_data.get('cards_list', [])
    if not cards or index >= len(cards):
        return

    from utils.helpers import rarity_emoji, get_skill_power
    card = cards[index]
    skill_power = get_skill_power(card.get('skill', ''))

    text = (
        f"🃏 <b>YOUR CARDS</b> ({index + 1}/{len(cards)})\n\n"
        f"{rarity_emoji(card.get('rarity', 'Common'))} <b>{card['name']}</b>\n"
        f"💪 Power: {format_coins(card['power'])}\n"
        f"🔥 Skill: {card.get('skill', 'None')} (+{skill_power})\n"
        f"⚡ Total: {format_coins(card['power'] + skill_power)}\n"
        f"💎 Rarity: {card.get('rarity', 'Common')}\n"
    )

    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"cards_prev_{index}"))
    if index < len(cards) - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"cards_next_{index}"))
    rows = [nav_row] if nav_row else []
    buttons = InlineKeyboardMarkup(rows) if rows else None

    if is_callback:
        query = update.callback_query
        try:
            if card.get('image_file_id'):
                await query.edit_message_media(
                    media=InputMediaPhoto(media=card['image_file_id'], caption=text, parse_mode="HTML"),
                    reply_markup=buttons
                )
            else:
                await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)
        except Exception:
            await query.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)
    else:
        if card.get('image_file_id'):
            await update.message.reply_photo(photo=card['image_file_id'], caption=text,
                                              parse_mode="HTML", reply_markup=buttons)
        else:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)


async def inventory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("inv_prev_"):
        index = max(0, int(data.split("_")[-1]) - 1)
        context.user_data['inv_index'] = index
        await show_inventory_char(update, context, index, is_callback=True)
    elif data.startswith("inv_next_"):
        chars = context.user_data.get('inv_chars', [])
        index = min(len(chars) - 1, int(data.split("_")[-1]) + 1)
        context.user_data['inv_index'] = index
        await show_inventory_char(update, context, index, is_callback=True)
    elif data.startswith("cards_prev_"):
        index = max(0, int(data.split("_")[-1]) - 1)
        context.user_data['cards_index'] = index
        await show_user_card(update, context, index, is_callback=True)
    elif data.startswith("cards_next_"):
        cards = context.user_data.get('cards_list', [])
        index = min(len(cards) - 1, int(data.split("_")[-1]) + 1)
        context.user_data['cards_index'] = index
        await show_user_card(update, context, index, is_callback=True)


# ===== LOOTBOX =====

async def cmd_lootbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")

    text = (
        f"🎁 <b>LOOTBOXES</b>\n\n"
        f"1. 📦 Basic Box — {format_coins(LOOTBOX_PRICES['basic'])} coins\n"
        f"2. 🥈 Silver Box — {format_coins(LOOTBOX_PRICES['silver'])} coins\n"
        f"3. 🥇 Gold Box — {format_coins(LOOTBOX_PRICES['gold'])} coins\n"
        f"4. 💎 Diamond Box — {format_coins(LOOTBOX_PRICES['diamond'])} coins\n\n"
        f"<b>Possible Rewards:</b>\n"
        f"• 💰 Coins (90%)\n"
        f"• 🃏 Random Card (60%)\n"
        f"• 🧬 Random Character (40%)\n\n"
        f"Select a box:"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Basic — 3,000", callback_data="loot_basic"),
         InlineKeyboardButton("🥈 Silver — 6,000", callback_data="loot_silver")],
        [InlineKeyboardButton("🥇 Gold — 12,000", callback_data="loot_gold"),
         InlineKeyboardButton("💎 Diamond — 24,000", callback_data="loot_diamond")],
    ])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)


async def lootbox_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    box_map = {
        "loot_basic": "basic",
        "loot_silver": "silver",
        "loot_gold": "gold",
        "loot_diamond": "diamond"
    }

    box_name = box_map.get(data)
    if not box_name:
        return

    price = LOOTBOX_PRICES[box_name]
    user_data = db.get_user(user_id)

    if (user_data['coins'] + user_data['bank']) < price:
        await query.answer(f"Not enough coins! Need {format_coins(price)}", show_alert=True)
        return

    if not db.deduct_coins(user_id, price):
        await query.answer("Not enough coins!", show_alert=True)
        return

    roll = random.randint(1, 100)
    box_display = {"basic": "📦 Basic", "silver": "🥈 Silver", "gold": "🥇 Gold", "diamond": "💎 Diamond"}[box_name]

    if roll <= 40:
        chars = db.get_all_characters()
        if chars:
            char = random.choice(chars)
            db.give_character_to_user(user_id, char['char_id'])
            result = f"🔥 <b>CHARACTER!</b>\n🧬 You got: <b>{char['name']}</b> ({char['rarity']})!"
        else:
            coins_win = random.randint(1000, 5000)
            db.add_coins(user_id, coins_win)
            result = f"💰 <b>COINS!</b>\nYou got: {format_coins(coins_win)} coins!"
    elif roll <= 60:
        cards = db.get_all_cards()
        if cards:
            card = random.choice(cards)
            db.give_card_to_user(user_id, card['card_id'])
            result = f"🃏 <b>CARD!</b>\nYou got: <b>{card['name']}</b> ({card['rarity']})!"
        else:
            coins_win = random.randint(1000, 5000)
            db.add_coins(user_id, coins_win)
            result = f"💰 <b>COINS!</b>\nYou got: {format_coins(coins_win)} coins!"
    else:
        coins_win = random.randint(1000, 5000)
        db.add_coins(user_id, coins_win)
        result = f"💰 <b>COINS!</b>\nYou got: {format_coins(coins_win)} coins!"

    text = f"🎁 You opened a {box_display} Box!\n\n{result}"
    await query.edit_message_text(text, parse_mode="HTML")


# ===== BATTLEPASS =====

async def cmd_battlepass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")
    data = db.get_user(user.id)

    bp_status = "✅ ACTIVE" if battlepass_active(data) else "❌ Inactive"
    if battlepass_active(data):
        from utils.helpers import format_time_remaining
        bp_status += f" (expires in {format_time_remaining(data['battlepass_expiry'])})"

    text = (
        f"🎟️ <b>BATTLE PASS</b>\n\n"
        f"Status: {bp_status}\n\n"
        f"<b>Packages:</b>\n"
        f"1️⃣ 1 Day — {format_coins(BATTLEPASS_PRICES['1'][1])} coins\n"
        f"2️⃣ 3 Days — {format_coins(BATTLEPASS_PRICES['2'][1])} coins\n"
        f"3️⃣ 6 Days — {format_coins(BATTLEPASS_PRICES['3'][1])} coins\n\n"
        f"<b>Benefits:</b>\n"
        f"✅ +10% raid rewards\n"
        f"✅ +10% daily rewards\n"
        f"✅ Free tournament entry\n\n"
        f"Use /buypass to purchase!"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_buypass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")

    text = (
        f"🎟️ <b>BUY BATTLE PASS</b>\n\n"
        f"Select duration:"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"1️⃣ 1 Day — {format_coins(BATTLEPASS_PRICES['1'][1])} coins", callback_data="bp_buy_1")],
        [InlineKeyboardButton(f"2️⃣ 3 Days — {format_coins(BATTLEPASS_PRICES['2'][1])} coins", callback_data="bp_buy_2")],
        [InlineKeyboardButton(f"3️⃣ 6 Days — {format_coins(BATTLEPASS_PRICES['3'][1])} coins", callback_data="bp_buy_3")],
    ])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)


async def battlepass_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("bp_buy_"):
        key = data.split("_")[-1]
        if key not in BATTLEPASS_PRICES:
            return

        days, cost = BATTLEPASS_PRICES[key]
        user_data = db.get_user(user_id)

        if not db.deduct_coins(user_id, cost):
            await query.answer(f"Not enough coins! Need {format_coins(cost)}", show_alert=True)
            return

        now = time.time()
        current_expiry = user_data.get('battlepass_expiry', 0)
        if current_expiry > now:
            new_expiry = current_expiry + days * 86400
        else:
            new_expiry = now + days * 86400

        db.update_user(user_id, battlepass_expiry=new_expiry)

        await query.edit_message_text(
            f"🎟️ <b>BATTLE PASS ACTIVATED!</b>\n\n"
            f"✅ Duration: {days} day(s)\n"
            f"💰 Cost: {format_coins(cost)} coins\n"
            f"⏳ Expires in: {days * 24} hours\n\n"
            f"Enjoy your benefits! +10% all rewards!",
            parse_mode="HTML"
        )


async def cmd_mypremium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")
    data = db.get_user(user.id)

    if battlepass_active(data):
        from utils.helpers import format_time_remaining
        remaining = format_time_remaining(data['battlepass_expiry'])
        text = f"💎 <b>PREMIUM STATUS</b>\n\n✅ Battle Pass: <b>ACTIVE</b>\n⏳ Expires in: {remaining}"
    else:
        text = f"💎 <b>PREMIUM STATUS</b>\n\n❌ No active premium\n\nUse /buypass to get Battle Pass!"

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_buypremium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_buypass(update, context)


async def cmd_bpreward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.username or "", user.first_name or "")
    data = db.get_user(user.id)

    if not battlepass_active(data):
        await update.message.reply_text("❌ You need an active Battle Pass! Use /buypass")
        return

    await update.message.reply_text(
        "🎁 <b>BATTLE PASS REWARDS</b>\n\n"
        "✅ +10% raid rewards (automatic)\n"
        "✅ +10% daily rewards (automatic)\n"
        "✅ Better lootbox chances\n\n"
        "Rewards are applied automatically when you play!",
        parse_mode="HTML"
    )


def get_handlers():
    return [
        CommandHandler("bank", cmd_bank),
        CommandHandler("deposit", cmd_deposit),
        CommandHandler("withdraw", cmd_withdraw),
        CommandHandler("dice", cmd_dice),
        CommandHandler("bet", cmd_bet),
        CommandHandler("rob", cmd_rob),
        CommandHandler("slots", cmd_slots),
        CommandHandler("flip", cmd_flip),
        CommandHandler("market", cmd_market),
        CommandHandler("inventory", cmd_inventory),
        CommandHandler("cards", cmd_cards),
        CommandHandler("lootbox", cmd_lootbox),
        CommandHandler("battlepass", cmd_battlepass),
        CommandHandler("buypass", cmd_buypass),
        CommandHandler("mypremium", cmd_mypremium),
        CommandHandler("buypremium", cmd_buypremium),
        CommandHandler("bpreward", cmd_bpreward),
        CommandHandler("buy", cmd_market),
        CommandHandler("sell", cmd_market),
        CallbackQueryHandler(market_callback, pattern="^mkt_"),
        CallbackQueryHandler(inventory_callback, pattern="^(inv_|cards_)"),
        CallbackQueryHandler(lootbox_callback, pattern="^loot_"),
        CallbackQueryHandler(battlepass_callback, pattern="^bp_"),
    ]
