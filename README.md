# telegram-navigator

**AI-powered navigator for Telegram channels — auto-indexing, topic classification, smart search, and digests.**

Automatically indexes Telegram channels, classifies posts into topics using Google Gemini, generates navigable tables of contents, and delivers periodic digests to subscribers. Supports English and Russian UI with per-user language detection.

[🇷🇺 Русский](README.ru.md)

## Features

- **Auto-indexing** — reads channel history via Telethon, stores posts in DB
- **AI classification** — Google Gemini groups posts into topics with descriptions
- **Table of contents** — generates compact, navigable TOC for each channel
- **Smart search** — hybrid search (keywords + semantics) within a channel or across all at once. Semantic search requires OpenAI embeddings
- **Digest subscriptions** — periodic summaries of new posts delivered to subscribers
- **i18n** — English / Russian UI, auto-detected from Telegram language with manual override
- **Flexible DB** — SQLite (default, zero-config) or Supabase (PostgreSQL + pgvector)

## Use Cases

- **Stay on top of multiple channels** — add all your favorite channels, get a brief digest every 3 hours with AI-generated summaries. Click through to read the original post if something catches your eye.
- **Explore a new channel** — just added an interesting channel? The bot builds a table of contents with the most popular, useful, and recent posts organized by topic — instead of scrolling through hundreds of posts.
- **Build a knowledge base** — index a curated set of Telegram channels and get a continuously updated, searchable knowledge base on any topic — AI, crypto, dev tools, whatever you follow.
- **Search & research** — need to find that one post about a specific tool or technique? Search within a single channel or across all of them at once — hybrid search considers both keywords and meaning.

## Quick Start (Docker)

```bash
git clone https://github.com/OlegTestov/telegram-navigator.git
cd telegram-navigator
cp .env.example .env
# Edit .env with your credentials (see Prerequisites below)
docker compose up -d bot
```

## Quick Start (Local)

```bash
git clone https://github.com/OlegTestov/telegram-navigator.git
cd telegram-navigator
make setup          # creates venv, installs deps, copies .env.example
# Edit .env with your credentials
make run            # starts the bot
```

## First Run

Once the bot is running:

1. **Open the bot** in Telegram and send `/start`
2. **Add a channel** — tap "Add channel" and send a link like `t.me/channelname`
3. **Run the scheduler** to index the channel (fetches posts, classifies them, generates TOC):
   ```bash
   # Docker
   docker compose run --rm scheduler
   # Local
   make scheduler
   ```
4. **View the result** — go back to the bot, select the channel, tap "Generate TOC"
5. **Set up hourly scheduling** so new posts are indexed automatically:
   ```
   # Add to crontab (crontab -e)
   0 * * * * cd /path/to/telegram-navigator && docker compose run --rm scheduler >> data/scheduler.log 2>&1
   ```

## Prerequisites

| Credential | How to get |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Create a bot via [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | Register at [my.telegram.org](https://my.telegram.org) |
| `TELEGRAM_SESSION_STRING` | Run `make session` locally (interactive, requires phone + OTP) |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) |
| `ADMIN_TELEGRAM_ID` | Send `/start` to [@userinfobot](https://t.me/userinfobot) |

> **Note:** `generate_session.py` must be run locally (not in Docker) — it requires interactive phone number and OTP input.

## Configuration

See [`.env.example`](.env.example) for all available environment variables with descriptions.

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot API token |
| `TELEGRAM_API_ID` | Yes | — | Telethon API ID |
| `TELEGRAM_API_HASH` | Yes | — | Telethon API hash |
| `TELEGRAM_SESSION_STRING` | Yes | — | Telethon session string |
| `GEMINI_API_KEY` | Yes | — | Google Gemini API key |
| `ADMIN_TELEGRAM_ID` | Yes | — | Admin's Telegram user ID |
| `GEMINI_MODEL` | No | `gemini-3-flash-preview` | Gemini model name |
| `DB_BACKEND` | No | `sqlite` | `sqlite` or `supabase` |
| `SQLITE_DB_PATH` | No | `data/content_table.db` | SQLite database path |
| `OPENAI_API_KEY` | No | — | Enables hybrid search (keywords + semantics) |

## Architecture

```
telegram-navigator/
├── src/
│   ├── main.py              # Bot entry point (long-running polling)
│   ├── scheduler_main.py    # Hourly cron: fetch → classify → score → TOC → digest
│   ├── bot/                  # Handlers, callbacks, keyboards, messages (i18n)
│   ├── config/               # Settings, constants, LLM prompts
│   ├── database/             # DB factory, models, SQLite & Supabase queries
│   ├── services/             # Fetcher, classifier, scorer, TOC generator, digest, embedder
│   └── utils/                # Helpers, i18n, error types
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── schema.sql                # Supabase schema (SQLite auto-creates)
```

**Two processes:**
1. **Bot** (`src.main`) — Telegram polling, handles user commands and callbacks
2. **Scheduler** (`src.scheduler_main`) — hourly pipeline: fetch new posts → classify → score → update TOC → send digests

## Deployment

See [docs/deployment.md](docs/deployment.md) for detailed instructions on:
- Docker (recommended)
- Heroku
- VPS / systemd
- Railway / Render / Fly.io

## Database

The bot supports two database backends. Set `DB_BACKEND` in `.env` to choose.

### SQLite (default)

Zero-config — the database is created automatically on first run at `data/content_table.db`.

```env
DB_BACKEND=sqlite
SQLITE_DB_PATH=data/content_table.db
```

For hybrid (vector + keyword) search, install the optional `sqlite-vec` extension (included in `requirements.txt`). Without it, only keyword search is available.

### Supabase (PostgreSQL)

For cloud/production deployments with persistent storage.

1. Create a project at [supabase.com](https://supabase.com)
2. Enable the `vector` extension: **Dashboard → Database → Extensions → search "vector" → Enable**
3. Go to **SQL Editor** and run the entire [`schema.sql`](schema.sql) — it creates all tables, indexes, the pgvector extension, and RPC functions for hybrid search
4. Set environment variables:

```env
DB_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and PR guidelines.

## Roadmap

- [ ] LLM abstraction layer (Claude, Ollama, OpenRouter)
- [ ] Multi-admin RBAC
- [ ] Test suite
- [ ] More languages (FILTERED, etc.)
- [ ] Per-channel language for TOC and LLM prompts

## License

[MIT](LICENSE)
