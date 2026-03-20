import re
import time
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.constants import ChatMemberStatus
import database as db

BAD_WORDS = [
    "madarchod", "madharchod",
    "bhenchod", "bhen chod", "bhnchd",
    "chutiya", "chutiye", "chut",
    "gandu", "gaand",
    "bsdk",
    "randi",
    "harami",
    "kutte ka",
    "sala", "saala",
]

MUTE_WARNINGS_LIMIT = 2

MUTE_COOLDOWNS = {}


def contains_abuse(text: str) -> bool:
    text = text.lower()
    for word in BAD_WORDS:
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, text):
            return True
    return False


async def abuse_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return

    user = update.effective_user
    if not user:
        return

    text = update.message.text

    if not contains_abuse(text):
        return

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return
    except Exception:
        return

    user_id = user.id
    chat_id = chat.id

    now = time.time()
    key = f"{user_id}_{chat_id}"
    if now - MUTE_COOLDOWNS.get(key, 0) < 10:
        return
    MUTE_COOLDOWNS[key] = now

    warns = db.get_warns(user_id, chat_id)
    warns += 1
    db.set_warns(user_id, chat_id, warns)

    user_mention = f"@{user.username}" if user.username else user.first_name or f"User {user_id}"

    if warns < MUTE_WARNINGS_LIMIT:
        await update.message.reply_text(
            f"⚠️ <b>WARNING {warns}/{MUTE_WARNINGS_LIMIT}</b>\n\n"
            f"{user_mention}, please avoid abusive language!\n"
            f"One more warning and you'll be muted for 1 hour. 🔇",
            parse_mode="HTML"
        )
    else:
        db.set_warns(user_id, chat_id, 0)

        try:
            from datetime import datetime, timedelta
            until = datetime.now() + timedelta(hours=1)
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=__import__('telegram').ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False,
                ),
                until_date=until
            )
            await update.message.reply_text(
                f"🔇 <b>{user_mention} has been muted for 1 hour!</b>\n\n"
                f"Reason: Repeated abusive language\n"
                f"Warnings reset. Next violation = another mute. ⚡",
                parse_mode="HTML"
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ <b>{user_mention}</b> would be muted but I don't have permission to restrict members!\n"
                f"Please make me an admin with restrict permissions.",
                parse_mode="HTML"
            )


async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        await update.message.reply_text("❌ This command only works in groups!")
        return

    requester = update.effective_user
    try:
        req_member = await context.bot.get_chat_member(chat.id, requester.id)
        if req_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            await update.message.reply_text("❌ Only admins can use this command!")
            return
    except Exception:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a user's message to warn them!")
        return

    target = update.message.reply_to_message.from_user
    if target.is_bot:
        await update.message.reply_text("❌ Can't warn bots!")
        return

    user_mention = f"@{target.username}" if target.username else target.first_name
    warns = db.get_warns(target.id, chat.id)
    warns += 1
    db.set_warns(target.id, chat.id, warns)

    if warns >= MUTE_WARNINGS_LIMIT:
        db.set_warns(target.id, chat.id, 0)
        try:
            from datetime import datetime, timedelta
            until = datetime.now() + timedelta(hours=1)
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=target.id,
                permissions=__import__('telegram').ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False,
                ),
                until_date=until
            )
            await update.message.reply_text(
                f"🔇 <b>{user_mention} muted for 1 hour</b> after reaching warning limit!\n\nWarnings reset.",
                parse_mode="HTML"
            )
        except Exception:
            await update.message.reply_text(
                f"⚠️ <b>{user_mention}</b> reached warning limit but I can't mute (need admin with restrict permission).",
                parse_mode="HTML"
            )
    else:
        reason = " ".join(context.args) if context.args else "No reason given"
        await update.message.reply_text(
            f"⚠️ <b>Warning {warns}/{MUTE_WARNINGS_LIMIT}</b>\n\n"
            f"User: {user_mention}\n"
            f"Reason: {reason}\n\n"
            f"Another warning = 1 hour mute!",
            parse_mode="HTML"
        )


async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        await update.message.reply_text("❌ This command only works in groups!")
        return

    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    else:
        target = update.effective_user

    warns = db.get_warns(target.id, chat.id)
    user_mention = f"@{target.username}" if target.username else target.first_name

    await update.message.reply_text(
        f"⚠️ <b>WARNINGS</b>\n\n"
        f"User: {user_mention}\n"
        f"Warns: {warns}/{MUTE_WARNINGS_LIMIT}\n\n"
        f"{'✅ All clear!' if warns == 0 else '⚠️ Be careful!' if warns == 1 else '🔴 Next = mute!'}",
        parse_mode="HTML"
    )


async def cmd_unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return

    requester = update.effective_user
    try:
        req_member = await context.bot.get_chat_member(chat.id, requester.id)
        if req_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            await update.message.reply_text("❌ Only admins can use this!")
            return
    except Exception:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a user to remove their warning!")
        return

    target = update.message.reply_to_message.from_user
    current = db.get_warns(target.id, chat.id)
    new_warns = max(0, current - 1)
    db.set_warns(target.id, chat.id, new_warns)

    user_mention = f"@{target.username}" if target.username else target.first_name
    await update.message.reply_text(
        f"✅ Warning removed from {user_mention}!\nWarnings: {new_warns}/{MUTE_WARNINGS_LIMIT}",
        parse_mode="HTML"
    )


async def cmd_resetwarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return

    requester = update.effective_user
    try:
        req_member = await context.bot.get_chat_member(chat.id, requester.id)
        if req_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            await update.message.reply_text("❌ Only admins can use this!")
            return
    except Exception:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a user to reset their warnings!")
        return

    target = update.message.reply_to_message.from_user
    db.set_warns(target.id, chat.id, 0)

    user_mention = f"@{target.username}" if target.username else target.first_name
    await update.message.reply_text(
        f"✅ Warnings reset for {user_mention}!", parse_mode="HTML"
    )


async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return

    requester = update.effective_user
    try:
        req_member = await context.bot.get_chat_member(chat.id, requester.id)
        if req_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            await update.message.reply_text("❌ Only admins can mute users!")
            return
    except Exception:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a user to mute them!\nUsage: /mute [1h/1d/forever]")
        return

    target = update.message.reply_to_message.from_user
    if target.is_bot:
        await update.message.reply_text("❌ Can't mute bots!")
        return

    duration_str = context.args[0].lower() if context.args else "1h"

    from datetime import datetime, timedelta
    import re

    until = None
    duration_text = "1 hour"

    m = re.match(r"(\d+)([hdm])", duration_str)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        if unit == "h":
            until = datetime.now() + timedelta(hours=amount)
            duration_text = f"{amount} hour(s)"
        elif unit == "d":
            until = datetime.now() + timedelta(days=amount)
            duration_text = f"{amount} day(s)"
        elif unit == "m":
            until = datetime.now() + timedelta(minutes=amount)
            duration_text = f"{amount} minute(s)"
    elif duration_str == "forever":
        until = None
        duration_text = "forever"
    else:
        until = datetime.now() + timedelta(hours=1)
        duration_text = "1 hour"

    user_mention = f"@{target.username}" if target.username else target.first_name

    try:
        import telegram
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target.id,
            permissions=telegram.ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
            ),
            until_date=until
        )
        await update.message.reply_text(
            f"🔇 <b>{user_mention} muted for {duration_text}!</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to mute: {e}")


async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return

    requester = update.effective_user
    try:
        req_member = await context.bot.get_chat_member(chat.id, requester.id)
        if req_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            await update.message.reply_text("❌ Only admins can unmute users!")
            return
    except Exception:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a user to unmute them!")
        return

    target = update.message.reply_to_message.from_user
    user_mention = f"@{target.username}" if target.username else target.first_name

    try:
        import telegram
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target.id,
            permissions=telegram.ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False,
            )
        )
        await update.message.reply_text(
            f"✅ <b>{user_mention} has been unmuted!</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to unmute: {e}")


def get_handlers():
    return [
        CommandHandler("warn", cmd_warn),
        CommandHandler("warns", cmd_warns),
        CommandHandler("unwarn", cmd_unwarn),
        CommandHandler("resetwarns", cmd_resetwarns),
        CommandHandler("mute", cmd_mute),
        CommandHandler("unmute", cmd_unmute),
        MessageHandler(filters.TEXT & ~filters.COMMAND, abuse_filter),
    ]
