# Contributing to telegram-navigator

Thank you for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/OlegTestov/telegram-navigator.git
cd telegram-navigator
make setup    # creates .venv, installs deps, copies .env.example
```

Edit `.env` with your test credentials, then:
```bash
make run      # starts the bot
```

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
make lint     # check for issues
make format   # auto-format
```

CI runs `ruff check src/` and `ruff format --check src/` on every push.

## Pull Request Process

1. Fork the repo and create a feature branch from `main`
2. Make your changes
3. Run `make lint` — ensure no errors
4. Submit a PR with a clear description of what and why

## Project Structure

| Directory | Purpose |
|---|---|
| `src/bot/` | Telegram handlers, callbacks, keyboards, localized messages |
| `src/services/` | Business logic: fetcher, classifier, TOC generator, digest |
| `src/database/` | DB factory, models, SQLite and Supabase query implementations |
| `src/config/` | Settings, constants, LLM prompts |
| `src/utils/` | Helpers, i18n, error types |

## Localization

- **UI strings** are in `src/bot/messages/` — one file per language (`ru.py`, `en.py`)
- **Keyboard labels** are `KB_*` constants in the same files
- **LLM prompts** are in `src/config/prompts.py` — these control content language, not user UI
- To add a new language: create `src/bot/messages/xx.py`, add it to `__init__.py`

## Good First Issues

- **LLM abstraction** — add support for Claude, Ollama, or OpenRouter alongside Gemini
- **More languages** — add UI translations (the i18n framework is ready)
- **Tests** — unit tests for services, integration tests for DB queries
