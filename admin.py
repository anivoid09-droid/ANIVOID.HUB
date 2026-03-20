import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import database as db
from utils.helpers import format_coins, format_time_remaining, get_display_name_from_db
from utils.buttons import admin_main_menu, back_to_admin
from config import ADMIN_ID


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ===== ADMIN MAIN =====

async def cmd_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access Denied.")
        return

    await update.message.reply_text(
        "🔥 <b>ANIVOID RPG — ADMIN PANEL</b>",
        reply_markup=admin_main_menu(),
        parse_mode="HTML"
    )


# ===== DASHBOARD =====

async def show_dashboard(query):
    total_users = db.count_users()
    total_groups = db.count_groups()
    chars = db.get_all_characters()
    cards = db.get_all_cards()
    ads = db.count_ads()
    guilds = db.count_guilds()

    t = db.get_ongoing_tournament()
    active_tournament = 1 if t else 0

    text = (
        f"📊 <b>DASHBOARD OVERVIEW</b>\n\n"
        f"👥 Total Users: {total_users}\n"
        f"📢 Total Groups: {total_groups}\n"
        f"🧬 Characters: {len(chars)}\n"
        f"🃏 Cards: {len(cards)}\n"
        f"📢 Active Ads: {ads}\n"
        f"🏆 Active Tournaments: {active_tournament}\n"
        f"🏰 Total Guilds: {guilds}"
    )

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_to_admin())


# ===== USERS PANEL =====

async def show_users_page(query, page=0):
    per_page = 10
    users = db.get_users_paginated(page, per_page)
    total = db.count_users()
    total_pages = max(1, (total + per_page - 1) // per_page)

    text = f"👥 <b>USERS LIST</b> (Page {page + 1}/{total_pages})\n\n"
    rows = []
    for i, u in enumerate(users):
        name = f"@{u['username']}" if u['username'] else u.get('first_name', f"User_{u['user_id']}")
        text += f"{page * per_page + i + 1}. {name} — Lv.{u['level']}\n"
        rows.append([InlineKeyboardButton(
            f"{name}",
            callback_data=f"admin_user_{u['user_id']}"
        )])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_users_{page - 1}"))
    if (page + 1) * per_page < total:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"admin_users_{page + 1}"))
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="admin_main")])

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


async def show_user_panel(query, user_id):
    u = db.get_user(user_id)
    if not u:
        await query.answer("User not found!", show_alert=True)
        return

    name = f"@{u['username']}" if u['username'] else u.get('first_name', 'Unknown')
    import datetime
    join = datetime.datetime.fromtimestamp(u['join_date']).strftime("%Y-%m-%d") if u.get('join_date') else "Unknown"

    text = (
        f"👤 <b>USER PANEL</b>\n\n"
        f"🧑 Username: {name}\n"
        f"🆔 ID: {user_id}\n"
        f"⭐ Level: {u['level']}\n"
        f"📊 XP: {format_coins(u['xp'])}\n"
        f"💰 Coins: {format_coins(u['coins'])}\n"
        f"🏦 Bank: {format_coins(u['bank'])}\n"
        f"🏅 Rank: {u['rank']}\n"
        f"🚫 Banned: {'Yes' if u.get('banned') else 'No'}\n"
        f"📅 Joined: {join}"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Level/XP", callback_data=f"uadmin_lvl_{user_id}"),
         InlineKeyboardButton("💰 Economy", callback_data=f"uadmin_eco_{user_id}")],
        [InlineKeyboardButton("💎 Premium", callback_data=f"uadmin_prem_{user_id}"),
         InlineKeyboardButton("🎒 Inventory", callback_data=f"uadmin_inv_{user_id}")],
        [InlineKeyboardButton("⚙️ Actions", callback_data=f"uadmin_act_{user_id}"),
         InlineKeyboardButton("🔙 Back", callback_data="admin_users_0")],
    ])

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)


# ===== CHARACTERS PANEL =====

async def show_characters_panel(query):
    chars = db.get_all_characters()
    text = f"🧬 <b>CHARACTERS PANEL</b>\n\n{len(chars)} total characters\n\n"
    for i, c in enumerate(chars[:15]):
        text += f"{i+1}. {c['name']} (Power: {format_coins(c['power'])}, {c['rarity']})\n"
    if len(chars) > 15:
        text += f"...and {len(chars) - 15} more"

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Character", callback_data="admin_add_character")],
        [InlineKeyboardButton("🗑️ Delete Character", callback_data="admin_del_char_0")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_main")],
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)


async def show_del_char_page(query, page=0):
    chars = db.get_all_characters()
    per_page = 10
    start = page * per_page
    end = min(start + per_page, len(chars))
    page_chars = chars[start:end]

    text = f"🗑️ <b>DELETE CHARACTER</b> (Page {page + 1})\n\nSelect character to delete:"
    rows = []
    for c in page_chars:
        rows.append([InlineKeyboardButton(
            f"🗑️ {c['name']} ({c['rarity']})",
            callback_data=f"admin_del_char_confirm_{c['char_id']}"
        )])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_del_char_{page - 1}"))
    if end < len(chars):
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"admin_del_char_{page + 1}"))
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="admin_characters")])

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


async def show_del_card_page(query, page=0):
    cards = db.get_all_cards()
    per_page = 10
    start = page * per_page
    end = min(start + per_page, len(cards))
    page_cards = cards[start:end]

    text = f"🗑️ <b>DELETE CARD</b> (Page {page + 1})\n\nSelect card to delete:"
    rows = []
    for c in page_cards:
        rows.append([InlineKeyboardButton(
            f"🗑️ {c['name']} ({c['rarity']})",
            callback_data=f"admin_del_card_confirm_{c['card_id']}"
        )])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_del_card_{page - 1}"))
    if end < len(cards):
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"admin_del_card_{page + 1}"))
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="admin_cards")])

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


# ===== ADS PANEL =====

async def show_ads_panel(query):
    ads = db.get_all_ads()
    text = f"📢 <b>ADS MANAGER</b>\n\n{len(ads)} total ads\n\n"
    for a in ads[:10]:
        status = "✅" if a['status'] == 'active' else "❌"
        text += f"{status} Ad #{a['ad_id']}: {a['text'][:30]}...\n"

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Ad", callback_data="admin_add_ad")],
        [InlineKeyboardButton("📋 View Ads", callback_data="admin_view_ads")],
        [InlineKeyboardButton("❌ Disable Ad", callback_data="admin_disable_ad"),
         InlineKeyboardButton("✅ Enable Ad", callback_data="admin_enable_ad")],
        [InlineKeyboardButton("🗑️ Delete Ad", callback_data="admin_delete_ad")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_main")],
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)


# ===== RAID BOSS PANEL =====

async def show_raid_boss_panel(query):
    bosses = db.get_all_raid_bosses()
    text = f"🐉 <b>RAID BOSSES</b>\n\n{len(bosses)} total raid bosses\n\n"
    for b in bosses[:10]:
        text += f"• Lv.{b['level']} {b['name']} (Power: {format_coins(b['power'])}, Reward: {format_coins(b['rewards'])})\n"

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Raid Boss", callback_data="admin_add_raid_boss")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_main")],
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)


# ===== GUILD BOSS PANEL =====

async def show_guild_boss_panel(query):
    bosses = db.get_bosses_by_type('guild_boss')
    text = f"🏰 <b>GUILD BOSSES</b>\n\n{len(bosses)} total guild bosses\n\n"
    for b in bosses:
        text += f"• {b['name']} (Power: {format_coins(b['power'])}, HP: {format_coins(b['health'])}, Reward: {format_coins(b['rewards'])})\n"

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Guild Boss", callback_data="admin_add_guild_boss")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_main")],
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)


# ===== TOURNAMENT PANEL =====

async def show_tournament_panel(query):
    t = db.get_ongoing_tournament()
    if t:
        count = db.count_tournament_participants(t['tournament_id'])
        text = (
            f"🏆 <b>TOURNAMENT PANEL</b>\n\n"
            f"Active Tournament #{t['tournament_id']}\n"
            f"Status: {t['status']}\n"
            f"Players: {count}/16\n"
            f"Reward: {format_coins(t['reward_coins'])} coins"
        )
    else:
        text = "🏆 <b>TOURNAMENT PANEL</b>\n\nNo active tournament."

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Create Tournament", callback_data="admin_create_tournament")],
        [InlineKeyboardButton("🔚 End Tournament", callback_data="admin_end_tournament")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_main")],
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)


# ===== MAIN CALLBACK HANDLER =====

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await query.answer("❌ Access Denied!", show_alert=True)
        return

    data = query.data

    if data == "admin_main":
        await query.edit_message_text("🔥 <b>ANIVOID RPG — ADMIN PANEL</b>",
                                       reply_markup=admin_main_menu(), parse_mode="HTML")

    elif data == "admin_dashboard":
        await show_dashboard(query)

    elif data.startswith("admin_users_"):
        page = int(data.split("_")[-1])
        await show_users_page(query, page)

    elif data.startswith("admin_user_"):
        uid = int(data.split("_")[-1])
        await show_user_panel(query, uid)

    elif data.startswith("uadmin_lvl_"):
        uid = int(data.split("_")[-1])
        context.user_data['admin_state'] = f'set_level_{uid}'
        await query.edit_message_text(
            f"📊 <b>SET LEVEL/XP</b>\n\nSend format:\n<code>level xp</code>\n\nExample:\n<code>10 1500</code>",
            parse_mode="HTML"
        )

    elif data.startswith("uadmin_eco_"):
        uid = int(data.split("_")[-1])
        context.user_data['admin_state'] = f'set_eco_{uid}'
        await query.edit_message_text(
            f"💰 <b>ECONOMY</b>\n\nSend format:\n<code>action amount</code>\n\nActions:\n"
            f"<code>add 5000</code> — Add coins\n"
            f"<code>remove 5000</code> — Remove coins\n"
            f"<code>bank 10000</code> — Set bank balance",
            parse_mode="HTML"
        )

    elif data.startswith("uadmin_prem_"):
        uid = int(data.split("_")[-1])
        context.user_data['admin_state'] = f'set_prem_{uid}'
        await query.edit_message_text(
            f"💎 <b>PREMIUM</b>\n\nSend format:\n<code>give days</code> or <code>remove</code>\n\nExample:\n<code>give 7</code>",
            parse_mode="HTML"
        )

    elif data.startswith("uadmin_inv_"):
        uid = int(data.split("_")[-1])
        context.user_data['admin_state'] = f'set_inv_{uid}'
        await query.edit_message_text(
            f"🎒 <b>INVENTORY</b>\n\nSend format:\n<code>add_char char_id</code> or <code>add_card card_id</code>\n\nExample:\n<code>add_char 1</code>",
            parse_mode="HTML"
        )

    elif data.startswith("uadmin_act_"):
        uid = int(data.split("_")[-1])
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 Ban User", callback_data=f"uadmin_ban_{uid}"),
             InlineKeyboardButton("✅ Unban User", callback_data=f"uadmin_unban_{uid}")],
            [InlineKeyboardButton("🔄 Reset Account", callback_data=f"uadmin_reset_{uid}")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"admin_user_{uid}")],
        ])
        await query.edit_message_text(f"⚙️ <b>ACTIONS for user {uid}</b>", parse_mode="HTML", reply_markup=buttons)

    elif data.startswith("uadmin_ban_"):
        uid = int(data.split("_")[-1])
        db.update_user(uid, banned=1)
        await query.edit_message_text(f"🚫 User {uid} has been banned.", reply_markup=back_to_admin())

    elif data.startswith("uadmin_unban_"):
        uid = int(data.split("_")[-1])
        db.update_user(uid, banned=0)
        await query.edit_message_text(f"✅ User {uid} has been unbanned.", reply_markup=back_to_admin())

    elif data.startswith("uadmin_reset_"):
        uid = int(data.split("_")[-1])
        db.update_user(uid, coins=0, bank=0, xp=0, level=1, rank='Bronze')
        await query.edit_message_text(f"🔄 User {uid} account reset.", reply_markup=back_to_admin())

    elif data == "admin_groups":
        groups = db.get_all_groups()
        text = f"📢 <b>GROUPS</b>\n\n{len(groups)} total groups\n\n"
        for g in groups[:15]:
            text += f"• {g.get('chat_title', 'Unknown')} (ID: {g['chat_id']})\n"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_to_admin())

    elif data == "admin_characters":
        await show_characters_panel(query)

    elif data == "admin_add_character":
        context.user_data['admin_state'] = 'add_character'
        await query.edit_message_text(
            "🧬 <b>ADD CHARACTER</b>\n\n"
            "Send an <b>image</b> with this caption:\n\n"
            "<code>Name: Gojo\n"
            "Power: 9000\n"
            "Skill: Infinity\n"
            "Rarity: SSR\n"
            "Description: Strongest sorcerer\n"
            "Price: 1500</code>",
            parse_mode="HTML"
        )

    elif data == "admin_cards":
        chars = db.get_all_cards()
        text = f"🃏 <b>CARDS PANEL</b>\n\n{len(chars)} total cards\n\n"
        for c in chars[:15]:
            text += f"{c['card_id']}. {c['name']} (Power: {format_coins(c['power'])}, {c['rarity']})\n"
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Card", callback_data="admin_add_card")],
            [InlineKeyboardButton("🗑️ Delete Card", callback_data="admin_del_card_0")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")],
        ])
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)

    elif data == "admin_add_card":
        context.user_data['admin_state'] = 'add_card'
        await query.edit_message_text(
            "🃏 <b>ADD CARD</b>\n\n"
            "Send an <b>image</b> with this caption:\n\n"
            "<code>Name: Mikasa\n"
            "Power: 7000\n"
            "Skill: Thunder Slash\n"
            "Rarity: Rare\n"
            "Description: Survey Corps ace\n"
            "Price: 1000</code>",
            parse_mode="HTML"
        )

    elif data == "admin_ads":
        await show_ads_panel(query)

    elif data == "admin_add_ad":
        context.user_data['admin_state'] = 'add_ad'
        await query.edit_message_text(
            "📢 <b>ADD AD</b>\n\n"
            "Send an image with caption (text of the ad), OR\n"
            "Just send the ad text (no image):",
            parse_mode="HTML"
        )

    elif data == "admin_view_ads":
        ads = db.get_all_ads()
        text = "📋 <b>ALL ADS</b>\n\n"
        for a in ads:
            status = "✅" if a['status'] == 'active' else "❌"
            text += f"#{a['ad_id']} {status} {a['text'][:50]}...\n\n"
        if not ads:
            text += "No ads yet."
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_to_admin())

    elif data == "admin_disable_ad":
        context.user_data['admin_state'] = 'disable_ad'
        await query.edit_message_text("❌ Send the Ad ID to disable:", reply_markup=back_to_admin())

    elif data == "admin_enable_ad":
        context.user_data['admin_state'] = 'enable_ad'
        await query.edit_message_text("✅ Send the Ad ID to enable:", reply_markup=back_to_admin())

    elif data == "admin_delete_ad":
        context.user_data['admin_state'] = 'delete_ad'
        await query.edit_message_text("🗑️ Send the Ad ID to delete:", reply_markup=back_to_admin())

    elif data == "admin_tournaments":
        await show_tournament_panel(query)

    elif data == "admin_create_tournament":
        t_id = db.create_tournament(reward_coins=50000, reward_xp=5000)
        await query.edit_message_text(
            f"✅ <b>TOURNAMENT CREATED!</b>\n\nTournament #{t_id}\nMax {16} players\nReward: 50,000 coins\n\nPlayers can join with /jointournament",
            parse_mode="HTML", reply_markup=back_to_admin()
        )

    elif data == "admin_end_tournament":
        t = db.get_ongoing_tournament()
        if not t:
            await query.answer("No active tournament!", show_alert=True)
            return
        from handlers.tournament import resolve_tournament
        participants = db.get_tournament_participants(t['tournament_id'])
        if participants:
            winner = max(participants, key=lambda p: p['power'])
            db.finish_tournament(t['tournament_id'], winner['user_id'])
            await query.edit_message_text(
                f"🏆 Tournament #{t['tournament_id']} ended!\nWinner: User {winner['user_id']}",
                reply_markup=back_to_admin()
            )
        else:
            db.finish_tournament(t['tournament_id'], 0)
            await query.edit_message_text("Tournament ended (no participants).", reply_markup=back_to_admin())

    elif data == "admin_market":
        items = db.get_market_items()
        text = f"🛒 <b>MARKET</b>\n\n{len(items)} items\n\nItems are added automatically when characters/cards are created."
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_to_admin())

    elif data == "admin_guilds":
        guilds = db.get_all_guilds()
        text = f"🏰 <b>GUILDS</b>\n\n{len(guilds)} total guilds\n\n"
        for g in guilds[:10]:
            text += f"• {g['name']} — {format_coins(g['guild_points'])} pts\n"
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ Delete Guild", callback_data="admin_del_guild")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")],
        ])
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=buttons)

    elif data == "admin_del_guild":
        context.user_data['admin_state'] = 'delete_guild'
        await query.edit_message_text("🗑️ Send guild ID to delete:", reply_markup=back_to_admin())

    elif data == "admin_raid_bosses":
        await show_raid_boss_panel(query)

    elif data == "admin_add_raid_boss":
        context.user_data['admin_state'] = 'add_raid_boss'
        await query.edit_message_text(
            "🐉 <b>ADD RAID BOSS</b>\n\n"
            "Send details in this format:\n\n"
            "<code>Name: Madara\n"
            "Power: 15000\n"
            "Skills: Eternal Mangekyou\n"
            "Level: 1\n"
            "Rewards: 5000</code>",
            parse_mode="HTML"
        )

    elif data == "admin_add_guild_boss":
        context.user_data['admin_state'] = 'add_guild_boss'
        await query.edit_message_text(
            "🏰 <b>ADD GUILD BOSS</b>\n\n"
            "Send an image with caption OR just text:\n\n"
            "<code>Name: Dragon Emperor\n"
            "Power: 50000\n"
            "Health: 500000\n"
            "Rewards: 20000\n"
            "Description: Ancient dragon boss</code>",
            parse_mode="HTML"
        )

    elif data == "admin_broadcast":
        context.user_data['admin_state'] = 'broadcast'
        await query.edit_message_text(
            "📣 <b>BROADCAST</b>\n\n"
            "Send an image with caption to broadcast to all groups, OR\n"
            "Send just text to broadcast without image:",
            parse_mode="HTML"
        )

    elif data == "admin_remove":
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 Delete Character", callback_data="admin_del_char_0")],
            [InlineKeyboardButton("🃏 Delete Card", callback_data="admin_del_card_0")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")],
        ])
        await query.edit_message_text("🗑️ <b>REMOVE ITEMS</b>", parse_mode="HTML", reply_markup=buttons)

    elif data.startswith("admin_del_char_confirm_"):
        char_id = int(data.split("_")[-1])
        char = db.get_character(char_id)
        if not char:
            await query.answer("Character not found!")
            return
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"admin_del_char_exec_{char_id}"),
             InlineKeyboardButton("❌ Cancel", callback_data="admin_del_char_0")],
        ])
        await query.edit_message_text(
            f"⚠️ Delete character <b>{char['name']}</b>?\n\nThis removes it from all users' inventories!",
            parse_mode="HTML", reply_markup=buttons
        )

    elif data.startswith("admin_del_char_exec_"):
        char_id = int(data.split("_")[-1])
        char = db.get_character(char_id)
        db.delete_character(char_id)
        await query.edit_message_text(
            f"✅ Character '{char['name'] if char else char_id}' deleted successfully!",
            reply_markup=back_to_admin()
        )

    elif data.startswith("admin_del_char_"):
        page = int(data.split("_")[-1])
        await show_del_char_page(query, page)

    elif data.startswith("admin_del_card_confirm_"):
        card_id = int(data.split("_")[-1])
        card = db.get_card(card_id)
        if not card:
            await query.answer("Card not found!")
            return
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"admin_del_card_exec_{card_id}"),
             InlineKeyboardButton("❌ Cancel", callback_data="admin_del_card_0")],
        ])
        await query.edit_message_text(
            f"⚠️ Delete card <b>{card['name']}</b>?\n\nThis removes it from all users' collections!",
            parse_mode="HTML", reply_markup=buttons
        )

    elif data.startswith("admin_del_card_exec_"):
        card_id = int(data.split("_")[-1])
        card = db.get_card(card_id)
        db.delete_card(card_id)
        await query.edit_message_text(
            f"✅ Card '{card['name'] if card else card_id}' deleted successfully!",
            reply_markup=back_to_admin()
        )

    elif data.startswith("admin_del_card_"):
        page = int(data.split("_")[-1])
        await show_del_card_page(query, page)


# ===== ADMIN MESSAGE HANDLER =====

async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return

    state = context.user_data.get('admin_state')
    if not state:
        return

    msg = update.message

    # ADD CHARACTER (image with caption)
    if state == 'add_character':
        if msg.photo:
            file_id = msg.photo[-1].file_id
            caption = msg.caption or ""
            from utils.helpers import parse_caption_fields
            fields = parse_caption_fields(caption)
            try:
                name = fields.get('name', 'Unknown')
                power = int(fields.get('power', 1000))
                skill = fields.get('skill', 'None')
                rarity = fields.get('rarity', 'Common')
                description = fields.get('description', '')
                price = int(fields.get('price', 1000))
                db.add_character(name, power, skill, file_id, description, rarity, price)
                context.user_data.pop('admin_state', None)
                await msg.reply_text(f"✅ Character <b>{name}</b> added to the game and market!", parse_mode="HTML")
            except Exception as e:
                await msg.reply_text(f"❌ Error: {e}\nCheck the format and try again.")
        else:
            await msg.reply_text("❌ Please send an image with the character details as caption!")

    # ADD CARD (image with caption)
    elif state == 'add_card':
        if msg.photo:
            file_id = msg.photo[-1].file_id
            caption = msg.caption or ""
            from utils.helpers import parse_caption_fields
            fields = parse_caption_fields(caption)
            try:
                name = fields.get('name', 'Unknown')
                power = int(fields.get('power', 500))
                skill = fields.get('skill', 'None')
                rarity = fields.get('rarity', 'Common')
                description = fields.get('description', '')
                price = int(fields.get('price', 500))
                db.add_card(name, power, skill, file_id, description, rarity, price)
                context.user_data.pop('admin_state', None)
                await msg.reply_text(f"✅ Card <b>{name}</b> added to the game and market!", parse_mode="HTML")
            except Exception as e:
                await msg.reply_text(f"❌ Error: {e}\nCheck the format and try again.")
        else:
            await msg.reply_text("❌ Please send an image with the card details as caption!")

    # ADD RAID BOSS (text)
    elif state == 'add_raid_boss':
        if msg.photo:
            # With image
            file_id = msg.photo[-1].file_id
            caption = msg.caption or ""
            from utils.helpers import parse_caption_fields
            fields = parse_caption_fields(caption)
        else:
            file_id = None
            from utils.helpers import parse_caption_fields
            fields = parse_caption_fields(msg.text or "")

        try:
            name = fields.get('name', 'Unknown Boss')
            power = int(fields.get('power', 10000))
            skills = fields.get('skills', 'Unknown')
            level = int(fields.get('level', 1))
            rewards = int(fields.get('rewards', 5000))
            db.add_raid_boss(name, power, skills, level, rewards)
            context.user_data.pop('admin_state', None)
            await msg.reply_text(f"✅ Raid Boss <b>{name}</b> added! (Lv.{level}, Power: {format_coins(power)})", parse_mode="HTML")
        except Exception as e:
            await msg.reply_text(f"❌ Error: {e}\nCheck the format and try again.")

    # ADD GUILD BOSS
    elif state == 'add_guild_boss':
        if msg.photo:
            file_id = msg.photo[-1].file_id
            caption = msg.caption or ""
            from utils.helpers import parse_caption_fields
            fields = parse_caption_fields(caption)
        else:
            file_id = None
            from utils.helpers import parse_caption_fields
            fields = parse_caption_fields(msg.text or "")

        try:
            name = fields.get('name', 'Guild Boss')
            power = int(fields.get('power', 50000))
            health = int(fields.get('health', 500000))
            rewards = int(fields.get('rewards', 20000))
            description = fields.get('description', '')
            db.add_boss(name, power, health, description, file_id, 'guild_boss', rewards)
            context.user_data.pop('admin_state', None)
            await msg.reply_text(f"✅ Guild Boss <b>{name}</b> added!", parse_mode="HTML")
        except Exception as e:
            await msg.reply_text(f"❌ Error: {e}")

    # ADD MAP
    elif state == 'add_map':
        from utils.helpers import parse_caption_fields
        if msg.photo:
            file_id = msg.photo[-1].file_id
            fields = parse_caption_fields(msg.caption or "")
        else:
            file_id = None
            fields = parse_caption_fields(msg.text or "")
        try:
            name = fields.get('name', 'Unknown Map')
            boss_count = int(fields.get('boss_count', 5))
            danger_level = int(fields.get('danger_level', 5))
            reward = int(fields.get('reward', 5000))
            db.add_map(name, boss_count, danger_level, reward, file_id)
            context.user_data.pop('admin_state', None)
            await msg.reply_text(f"✅ Map <b>{name}</b> added!", parse_mode="HTML")
        except Exception as e:
            await msg.reply_text(f"❌ Error: {e}")

    # ADD AD
    elif state == 'add_ad':
        if msg.photo:
            file_id = msg.photo[-1].file_id
            text = msg.caption or "Advertisement"
        else:
            file_id = None
            text = msg.text or "Advertisement"

        db.add_ad(text, file_id, user.id)
        context.user_data.pop('admin_state', None)
        await msg.reply_text("✅ Ad added and activated!")

    # BROADCAST
    elif state == 'broadcast':
        groups = db.get_all_groups()
        if not groups:
            await msg.reply_text("❌ No groups registered!")
            context.user_data.pop('admin_state', None)
            return

        sent = 0
        failed = 0
        for g in groups:
            try:
                if msg.photo:
                    await context.bot.send_photo(
                        chat_id=g['chat_id'],
                        photo=msg.photo[-1].file_id,
                        caption=msg.caption or "",
                        parse_mode="HTML"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=g['chat_id'],
                        text=msg.text or "",
                        parse_mode="HTML"
                    )
                sent += 1
            except Exception:
                failed += 1

        context.user_data.pop('admin_state', None)
        await msg.reply_text(f"📣 Broadcast complete!\n✅ Sent: {sent}\n❌ Failed: {failed}")

    # DISABLE/ENABLE/DELETE AD
    elif state in ('disable_ad', 'enable_ad', 'delete_ad'):
        try:
            ad_id = int(msg.text.strip())
            if state == 'disable_ad':
                db.toggle_ad(ad_id, 'inactive')
                await msg.reply_text(f"❌ Ad #{ad_id} disabled.")
            elif state == 'enable_ad':
                db.toggle_ad(ad_id, 'active')
                await msg.reply_text(f"✅ Ad #{ad_id} enabled.")
            elif state == 'delete_ad':
                db.delete_ad(ad_id)
                await msg.reply_text(f"🗑️ Ad #{ad_id} deleted.")
            context.user_data.pop('admin_state', None)
        except ValueError:
            await msg.reply_text("❌ Invalid ID!")

    # DELETE GUILD
    elif state == 'delete_guild':
        try:
            guild_id = int(msg.text.strip())
            db.delete_guild(guild_id)
            context.user_data.pop('admin_state', None)
            await msg.reply_text(f"✅ Guild {guild_id} deleted.")
        except ValueError:
            await msg.reply_text("❌ Invalid ID!")

    # SET LEVEL/XP
    elif state and state.startswith('set_level_'):
        uid = int(state.split('_')[-1])
        try:
            parts = msg.text.strip().split()
            level = int(parts[0])
            xp = int(parts[1])
            from config import get_rank
            db.update_user(uid, level=level, xp=xp, rank=get_rank(level))
            context.user_data.pop('admin_state', None)
            await msg.reply_text(f"✅ User {uid} level set to {level}, XP to {xp}!")
        except Exception:
            await msg.reply_text("❌ Format: <code>level xp</code>", parse_mode="HTML")

    # SET ECONOMY
    elif state and state.startswith('set_eco_'):
        uid = int(state.split('_')[-1])
        try:
            parts = msg.text.strip().split()
            action = parts[0].lower()
            amount = int(parts[1])
            if action == 'add':
                db.add_coins(uid, amount)
                await msg.reply_text(f"✅ Added {format_coins(amount)} coins to user {uid}!")
            elif action == 'remove':
                db.add_coins(uid, -amount)
                await msg.reply_text(f"✅ Removed {format_coins(amount)} coins from user {uid}!")
            elif action == 'bank':
                db.update_user(uid, bank=amount)
                await msg.reply_text(f"✅ Bank balance set to {format_coins(amount)} for user {uid}!")
            context.user_data.pop('admin_state', None)
        except Exception:
            await msg.reply_text("❌ Format: <code>add/remove/bank amount</code>", parse_mode="HTML")

    # SET PREMIUM
    elif state and state.startswith('set_prem_'):
        uid = int(state.split('_')[-1])
        try:
            parts = msg.text.strip().split()
            action = parts[0].lower()
            if action == 'give':
                days = int(parts[1])
                expiry = time.time() + days * 86400
                db.update_user(uid, battlepass_expiry=expiry)
                await msg.reply_text(f"✅ Given {days} day(s) premium to user {uid}!")
            elif action == 'remove':
                db.update_user(uid, battlepass_expiry=0.0)
                await msg.reply_text(f"✅ Premium removed from user {uid}!")
            context.user_data.pop('admin_state', None)
        except Exception:
            await msg.reply_text("❌ Format: <code>give days</code> or <code>remove</code>", parse_mode="HTML")

    # SET INVENTORY
    elif state and state.startswith('set_inv_'):
        uid = int(state.split('_')[-1])
        try:
            parts = msg.text.strip().split()
            action = parts[0].lower()
            item_id = int(parts[1])
            if action == 'add_char':
                db.give_character_to_user(uid, item_id)
                await msg.reply_text(f"✅ Character {item_id} given to user {uid}!")
            elif action == 'add_card':
                db.give_card_to_user(uid, item_id)
                await msg.reply_text(f"✅ Card {item_id} given to user {uid}!")
            elif action == 'remove_char':
                conn = db.get_conn()
                conn.execute("DELETE FROM user_characters WHERE user_id = ? AND char_id = ?", (uid, item_id))
                conn.commit()
                conn.close()
                await msg.reply_text(f"✅ Character {item_id} removed from user {uid}!")
            context.user_data.pop('admin_state', None)
        except Exception as e:
            await msg.reply_text(f"❌ Error: {e}")


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access Denied.")
        return
    context.user_data['admin_state'] = 'broadcast'
    await update.message.reply_text(
        "📣 <b>BROADCAST</b>\n\nSend image with caption or text to broadcast to all groups:",
        parse_mode="HTML"
    )


def get_handlers():
    return [
        CommandHandler("admins", cmd_admins),
        CommandHandler("broadcast", cmd_broadcast),
        CallbackQueryHandler(admin_callback, pattern="^(admin_|uadmin_)"),
        MessageHandler(filters.ALL & ~filters.COMMAND, admin_message_handler),
    ]
