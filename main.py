import logging
import sys
import os
import time

# Set path so modules can be found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
from config import BOT_TOKEN, ADMIN_ID, AD_INTERVAL_HOURS

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ===== AUTO-AD SENDER =====

async def send_scheduled_ads(bot):
    ads = db.get_active_ads()
    if not ads:
        return

    groups = db.get_all_groups()
    if not groups:
        return

    import random
    ad = random.choice(ads)

    for group in groups:
        try:
            if ad.get('image_file_id'):
                await bot.send_photo(
                    chat_id=group['chat_id'],
                    photo=ad['image_file_id'],
                    caption=ad['text'],
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=group['chat_id'],
                    text=ad['text'],
                    parse_mode="HTML"
                )
            db.update_group_ad_time(group['chat_id'])
        except Exception as e:
            logger.warning(f"Failed to send ad to {group['chat_id']}: {e}")


# ===== GROUP TRACKER =====

async def track_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        db.register_group(chat.id, chat.title or "Unknown")


# ===== UNKNOWN COMMAND =====

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Unknown command. Use /start to see all commands.")


# ===== MAIN =====

scheduler = AsyncIOScheduler()


async def post_init(application):
    scheduler.add_job(
        send_scheduled_ads,
        'interval',
        hours=AD_INTERVAL_HOURS,
        args=[application.bot],
        id='ad_sender',
        misfire_grace_time=60
    )
    scheduler.start()
    logger.info(f"✅ Ad scheduler started (every {AD_INTERVAL_HOURS} hours)")


async def post_stop(application):
    if scheduler.running:
        scheduler.shutdown(wait=False)


def main():
    logger.info("🚀 Starting ANIVOID RPG Bot...")

    # Init DB
    db.init_db()
    logger.info("✅ Database initialized.")

    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not set!")
        sys.exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).post_stop(post_stop).build()

    # Import all handlers
    from handlers import profile, explore, raid, cards, guild, tournament, economy, admin, aivra, moderation

    # Register command handlers first
    for h in profile.get_handlers():
        app.add_handler(h)

    for h in explore.get_handlers():
        app.add_handler(h)

    for h in raid.get_handlers():
        app.add_handler(h)

    for h in cards.get_handlers():
        app.add_handler(h)

    for h in guild.get_handlers():
        app.add_handler(h)

    for h in tournament.get_handlers():
        app.add_handler(h)

    for h in economy.get_handlers():
        app.add_handler(h)

    # AIVRA AI — commands + callback (but NOT the text handler yet)
    aivra_handlers = aivra.get_handlers()
    for h in aivra_handlers[:-1]:
        app.add_handler(h)

    # Moderation — commands first, abuse filter text handler second-to-last
    mod_handlers = moderation.get_handlers()
    for h in mod_handlers[:-1]:
        app.add_handler(h)

    # Admin handler — commands registered, message handler held for last
    admin_handlers = admin.get_handlers()
    for h in admin_handlers[:-1]:
        app.add_handler(h)

    # Group tracker — runs for all messages
    app.add_handler(MessageHandler(filters.ALL, track_group), group=1)

    # Unknown command
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # Moderation abuse filter (group-only, safe filter)
    app.add_handler(mod_handlers[-1], group=10)

    # AIVRA auto-reply (lowest priority text handler)
    app.add_handler(aivra_handlers[-1], group=20)

    # Admin message state handler (catch-all — must be very last)
    app.add_handler(admin_handlers[-1], group=99)

    logger.info("✅ All handlers registered.")
    logger.info("🤖 Bot is running...")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
