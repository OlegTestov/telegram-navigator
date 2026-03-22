# content-table

Telegram Channel TOC Bot — автоматическое оглавление каналов по темам.

## Tech Stack
- Python 3.12+, python-telegram-bot >= 21.0, Telethon 1.36.0
- Google Gemini (gemini-2.0-flash) для классификации
- Supabase PostgreSQL
- Heroku (worker + scheduler)

## Structure
- `src/main.py` — bot entry point (worker)
- `src/scheduler_main.py` — hourly cron entry point
- `src/config/` — settings, constants, prompts
- `src/database/` — Supabase client, models, queries
- `src/services/` — fetcher, classifier, scorer, toc_generator
- `src/bot/` — handlers, callbacks, keyboards, messages

## Running
```bash
# Bot (persistent worker)
python -m src.main

# Scheduler (hourly cron)
python -m src.scheduler_main

# Generate Telethon session
python generate_session.py
```

## Database
Tables prefixed with `ct_`: ct_channels, ct_posts, ct_topics, ct_post_topics.
Schema SQL in `schema.sql`.
