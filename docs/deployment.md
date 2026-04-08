# Deployment Guide

## Prerequisites

Before deploying, you need to generate a Telethon session string:

```bash
make session
# or: python generate_session.py
```

This is **interactive** — it asks for your phone number and a Telegram OTP code. Always run it locally, never in Docker or CI.

---

## Docker (Recommended)

The simplest way to deploy. Uses SQLite by default — no external database needed.

```bash
cp .env.example .env
# Edit .env with your credentials

# Start the bot
docker compose up -d bot

# Run the scheduler (hourly indexing pipeline)
docker compose run --rm scheduler
```

**Scheduler via cron** (recommended):
```
0 * * * * cd /path/to/telegram-navigator && docker compose run --rm scheduler >> data/scheduler.log 2>&1
```

Data persists in the `./data/` directory via Docker volume mount.

By default, Docker uses SQLite. To use Supabase instead, set in your `.env`:
```env
DB_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
```
And run [`schema.sql`](../schema.sql) in the Supabase SQL Editor before first start.

---

## Heroku

### Setup

```bash
heroku create your-app-name
heroku config:set TELEGRAM_BOT_TOKEN=... TELEGRAM_API_ID=... # etc.
git push heroku main  # or master, depending on your branch name
```

The included `Procfile` runs the bot as a worker process.

### Scheduler

Install the [Heroku Scheduler](https://elements.heroku.com/addons/scheduler) add-on:
```bash
heroku addons:create scheduler:standard
```

Add a job that runs every hour:
```
python -m src.scheduler_main
```

### Database

- Default: SQLite (stored in ephemeral filesystem — data lost on dyno restart)
- Recommended: Set `DB_BACKEND=supabase` with a Supabase project for persistent storage

---

## VPS / systemd

### Bot service

Create `/etc/systemd/system/telegram-navigator.service`:

```ini
[Unit]
Description=Telegram Navigator Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/telegram-navigator
EnvironmentFile=/opt/telegram-navigator/.env
ExecStart=/opt/telegram-navigator/.venv/bin/python -m src.main
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable telegram-navigator
sudo systemctl start telegram-navigator
```

### Scheduler via cron

```
0 * * * * cd /opt/telegram-navigator && .venv/bin/python -m src.scheduler_main >> data/scheduler.log 2>&1
```

---

## Railway / Render / Fly.io

The included `Dockerfile` works on all container-based platforms:

1. Connect your GitHub repo
2. Set environment variables in the platform dashboard
3. Deploy

For the scheduler, use the platform's cron/job feature or run it as a separate service with the command:
```
python -m src.scheduler_main
```
