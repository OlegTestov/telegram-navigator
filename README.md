# telegram-navigator

**AI-powered table-of-contents bot for Telegram channels.**

Automatically indexes Telegram channels, classifies posts into topics using Google Gemini, generates navigable tables of contents, and delivers periodic digests to subscribers. Supports English and Russian UI with per-user language detection.

[🇷🇺 Русский](README.ru.md)

## Features

- **Auto-indexing** — reads channel history via Telethon, stores posts in DB
- **AI classification** — Google Gemini groups posts into topics with descriptions
- **Table of contents** — generates compact, navigable TOC for each channel
- **Smart search** — keyword + vector hybrid search (optional OpenAI embeddings)
- **Digest subscriptions** — periodic summaries of new posts delivered to subscribers
- **i18n** — English / Russian UI, auto-detected from Telegram language with manual override
- **Flexible DB** — SQLite (default, zero-config) or Supabase (PostgreSQL + pgvector)

## Use Cases

- **Stay on top of multiple channels** — add all your favorite channels, get a brief digest every 3 hours with AI-generated summaries. Click through to read the original post if something catches your eye.
- **Explore a new channel** — just added an interesting channel? The bot builds a table of contents with the most popular, useful, and recent posts organized by topic. Skim the highlights instead of scrolling through hundreds of posts.
- **Build a knowledge base** — index a curated set of Telegram channels and get a continuously updated, searchable knowledge base on any topic — AI, crypto, dev tools, whatever you follow.
- **Search & research** — need to find that one post about a specific tool or technique? Search across all your channels at once with hybrid keyword + semantic search.

## Quick Start (Docker)

```bash
cp .env.example .env
# Edit .env with your credentials (see Prerequisites below)
docker compose up -d bot
```

Run the scheduler periodically (cron recommended):
```bash
docker compose run --rm scheduler
```

## Quick Start (Local)

```bash
make setup          # creates venv, installs deps, copies .env.example
# Edit .env with your credentials
make run            # starts the bot
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
| `OPENAI_API_KEY` | No | — | Enables hybrid vector search |

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
2. Go to **SQL Editor** and run the contents of [`schema.sql`](schema.sql)
3. Set environment variables:

```env
DB_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
```

Supabase uses pgvector for hybrid search — enable the `vector` extension in your project settings (Dashboard → Database → Extensions).

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
