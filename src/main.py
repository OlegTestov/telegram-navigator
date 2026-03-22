"""Main entry point for content-table Telegram Bot."""

import logging
import sys

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from src.config.settings import TELEGRAM_BOT_TOKEN, validate_config
from src.database.factory import create_queries
from src.bot.handlers import (
    start_command,
    help_command,
    channels_command,
    stats_command,
    search_command,
    handle_text_message,
)
from src.bot.callbacks import handle_callback

logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    """Initialize bot commands and shared resources."""
    # Set up database
    application.bot_data["queries"] = create_queries()

    await application.bot.set_my_commands([
        BotCommand("start", "🏠 Начало"),
        BotCommand("channels", "📢 Список каналов"),
        BotCommand("search", "🔍 Поиск по постам"),
        BotCommand("stats", "📊 Статистика"),
        BotCommand("help", "📖 Помощь"),
    ])
    logger.info("Bot initialized")


def create_application() -> Application:
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("channels", channels_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("search", search_command))

    # Callback query handler (all inline buttons)
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Text message handler (channel/post URLs)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )

    return application


def main() -> None:
    logger.info("=" * 40)
    logger.info("Starting content-table bot...")
    logger.info("=" * 40)

    try:
        validate_config()
        application = create_application()
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.critical("Bot failed to start: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
