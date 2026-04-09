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

The project has two localization layers:

- **UI strings** — `src/bot/messages/` (one file per language: `ru.py`, `en.py`)
- **Content translations** — LLM-generated content (post descriptions, topic names, TOC, digests) is generated in a configurable primary language (English by default) and automatically translated to other languages via Gemini. Translations are stored in per-entity translation tables (`ct_post_translations`, `ct_topic_translations`, etc.) — adding a new language requires no schema changes.

### Adding a new language (example: Spanish)

**Step 1.** Create `src/bot/messages/es.py` — copy `en.py` and translate all constants to Spanish. All constants must match the ones in `ru.py` and `en.py`.

**Step 2.** Register the language in `src/bot/messages/__init__.py`:

```python
from src.bot.messages import en, es, ru

_LANGS = {"ru": ru, "en": en, "es": es}
```

**Step 3.** Add a language button in `src/bot/callbacks.py` (the `set_lang` handler):

```python
InlineKeyboardButton("🇪🇸 Español", callback_data="lang:es"),
```

**Step 4.** Add bot command descriptions in `src/main.py` (`post_init`):

```python
await application.bot.set_my_commands(es_commands, language_code="es")
```

**Step 5.** Add content translation in `src/scheduler_main.py` — after each existing `translate_texts(...)` call, add a similar call for `"es"`:

```python
descriptions_es = await translate_texts(descriptions_ru, target_lang="Spanish")
queries.save_post_translations([(pid, "es", d) for (pid, _), d in zip(items, descriptions_es)])
```

Same pattern for topic names, topic summaries, TOC, and digests.

**Step 6.** Run the migration script to translate existing content:

```bash
# Edit scripts/translate_existing.py to include "es" alongside "en"
python -m scripts.translate_existing
```

No database schema changes required — the translation tables store any language code.

## Good First Issues

- **LLM abstraction** — add support for Claude, Ollama, or OpenRouter alongside Gemini
- **More languages** — add UI translations and content translation (the framework is ready, see above)
- **Tests** — unit tests for services, integration tests for DB queries
