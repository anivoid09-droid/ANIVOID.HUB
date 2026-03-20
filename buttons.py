from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def make_keyboard(rows):
    return InlineKeyboardMarkup(rows)


def nav_buttons(index: int, total: int, prefix: str, extra_buttons=None):
    row = []
    if index > 0:
        row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}_prev_{index}"))
    if index < total - 1:
        row.append(InlineKeyboardButton("➡️ Next", callback_data=f"{prefix}_next_{index}"))
    buttons = [row] if row else []
    if extra_buttons:
        buttons.extend(extra_buttons)
    return InlineKeyboardMarkup(buttons)


def map_selection_buttons(index: int, total: int):
    row = []
    if total > 1:
        if index > 0:
            row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"map_prev_{index}"))
        if index < total - 1:
            row.append(InlineKeyboardButton("➡️ Next", callback_data=f"map_next_{index}"))
    select_row = [InlineKeyboardButton("✅ Select This Map", callback_data=f"map_select_{index}")]
    return InlineKeyboardMarkup([row, select_row] if row else [select_row])


def char_selection_buttons(index: int, total: int, prefix: str = "char"):
    row = []
    if total > 1:
        if index > 0:
            row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}_prev_{index}"))
        if index < total - 1:
            row.append(InlineKeyboardButton("➡️ Next", callback_data=f"{prefix}_next_{index}"))
    select_row = [InlineKeyboardButton("✅ Select", callback_data=f"{prefix}_select_{index}")]
    return InlineKeyboardMarkup([row, select_row] if row else [select_row])


def confirm_buttons(confirm_data: str, cancel_data: str = "cancel"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data=confirm_data),
            InlineKeyboardButton("❌ Cancel", callback_data=cancel_data),
        ]
    ])


def card_selection_buttons(index: int, total: int, prefix: str = "mycard"):
    row = []
    if total > 1:
        if index > 0:
            row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}_prev_{index}"))
        if index < total - 1:
            row.append(InlineKeyboardButton("➡️ Next", callback_data=f"{prefix}_next_{index}"))
    select_row = [InlineKeyboardButton("⚔️ Fight with this card!", callback_data=f"{prefix}_select_{index}")]
    return InlineKeyboardMarkup([row, select_row] if row else [select_row])


def market_item_buttons(item_id: int, item_type: str, index: int, total: int):
    nav_row = []
    if total > 1:
        if index > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"mkt_prev_{index}"))
        if index < total - 1:
            nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"mkt_next_{index}"))
    buy_row = [InlineKeyboardButton("🛒 Buy", callback_data=f"mkt_buy_{item_type}_{item_id}")]
    rows = []
    if nav_row:
        rows.append(nav_row)
    rows.append(buy_row)
    return InlineKeyboardMarkup(rows)


def admin_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard")],
        [InlineKeyboardButton("👥 Users", callback_data="admin_users_0"),
         InlineKeyboardButton("📢 Groups", callback_data="admin_groups")],
        [InlineKeyboardButton("🧬 Characters", callback_data="admin_characters"),
         InlineKeyboardButton("🃏 Cards", callback_data="admin_cards")],
        [InlineKeyboardButton("📢 Ads Manager", callback_data="admin_ads"),
         InlineKeyboardButton("🏆 Tournaments", callback_data="admin_tournaments")],
        [InlineKeyboardButton("🛒 Market", callback_data="admin_market"),
         InlineKeyboardButton("🏰 Guilds", callback_data="admin_guilds")],
        [InlineKeyboardButton("🐉 Raid Bosses", callback_data="admin_raid_bosses"),
         InlineKeyboardButton("📣 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🗑️ Remove Items", callback_data="admin_remove")],
    ])


def back_to_admin():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_main")]
    ])
