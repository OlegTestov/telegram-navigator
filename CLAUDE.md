# telegram-navigator

AI-powered table-of-contents bot for Telegram channels.

## Tech Stack
- Python 3.12+, python-telegram-bot >= 21.0, Telethon 1.36.0
- Google Gemini (gemini-3-flash-preview) for classification & digests
- SQLite (default) or Supabase PostgreSQL
- Docker / Heroku / any VPS

## Structure
- `src/main.py` — bot entry point (long-running polling)
- `src/scheduler_main.py` — hourly cron entry point
- `src/config/` — settings, constants, LLM prompts
- `src/database/` — DB factory, models, SQLite & Supabase queries
- `src/services/` — fetcher, classifier, scorer, toc_generator, digest, embedder
- `src/bot/` — handlers, callbacks, keyboards
- `src/bot/messages/` — i18n package (ru.py, en.py)
- `src/utils/` — helpers, i18n, error types

## Running
```bash
make setup    # venv + deps
make run      # start bot
make scheduler  # run scheduler once
make session  # generate Telethon session string
```

## Database
Tables prefixed with `ct_`: ct_channels, ct_posts, ct_topics, ct_post_topics,
ct_user_subscriptions, ct_channel_digests, ct_digest_deliveries, ct_user_preferences.
Schema SQL in `schema.sql`. SQLite auto-creates tables via SCHEMA_SQL in sqlite_queries.py.

## i18n
- UI strings: `src/bot/messages/ru.py` and `en.py`, accessed via `get_messages(lang)`
- Language detection: `src/utils/i18n.py` — cache -> DB -> Telegram auto-detect -> 'ru'
- LLM prompts in `src/config/prompts.py` are NOT localized (tied to content language)
- TOC is cached per-channel, not per-user language

## Code Style
- `ruff check src/` and `ruff format src/`
- Line length: 120
