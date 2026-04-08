# telegram-navigator

**AI-навигатор по Telegram-каналам — авто-индексация, классификация по темам, умный поиск и дайджесты.**

Автоматически индексирует Telegram-каналы, классифицирует посты по темам с помощью Google Gemini, генерирует навигируемое оглавление и отправляет периодические дайджесты подписчикам. Поддерживает английский и русский интерфейс с автоопределением языка.

[🇬🇧 English](README.md)

## Возможности

- **Авто-индексация** — читает историю канала через Telethon, сохраняет посты в БД
- **AI-классификация** — Google Gemini группирует посты по темам с описаниями
- **Оглавление** — генерирует компактное навигируемое оглавление для каждого канала
- **Умный поиск** — ключевые слова + векторный гибридный поиск (опциональные OpenAI embeddings)
- **Подписки на дайджест** — периодические сводки новых постов для подписчиков
- **i18n** — английский / русский интерфейс, автоопределение из Telegram с ручным переключением
- **Гибкая БД** — SQLite (по умолчанию, без настройки) или Supabase (PostgreSQL + pgvector)

## Сценарии использования

- **Следить за множеством каналов** — добавьте все интересные каналы, каждые 3 часа получайте краткую сводку с AI-саммари. Заинтересовало — кликните и перейдите к оригинальному посту.
- **Изучить новый канал** — добавили интересный канал? Бот составит оглавление с самыми популярными, полезными и актуальными постами, разбитыми по темам. Пробегитесь по хайлайтам вместо прокрутки сотен постов.
- **Собрать базу знаний** — индексируйте набор Telegram-каналов и получите постоянно обновляемую, доступную для поиска базу знаний по любой теме — AI, крипто, dev-инструменты, что угодно.
- **Поиск и исследования** — нужно найти тот самый пост про конкретный инструмент? Ищите сразу по всем каналам с гибридным поиском (ключевые слова + семантика).

## Быстрый старт (Docker)

```bash
git clone https://github.com/OlegTestov/telegram-navigator.git
cd telegram-navigator
cp .env.example .env
# Заполните .env (см. Требования ниже)
docker compose up -d bot
```

## Быстрый старт (локально)

```bash
git clone https://github.com/OlegTestov/telegram-navigator.git
cd telegram-navigator
make setup          # создаёт venv, устанавливает зависимости, копирует .env.example
# Заполните .env
make run            # запускает бота
```

## Первый запуск

Когда бот запущен:

1. **Откройте бота** в Telegram и отправьте `/start`
2. **Добавьте канал** — нажмите "Добавить канал" и отправьте ссылку вида `t.me/channelname`
3. **Запустите планировщик** для индексации канала (загрузка постов, классификация, генерация TOC):
   ```bash
   # Docker
   docker compose run --rm scheduler
   # Локально
   make scheduler
   ```
4. **Посмотрите результат** — вернитесь в бота, выберите канал, нажмите "Создать оглавление"
5. **Настройте часовой запуск**, чтобы новые посты индексировались автоматически:
   ```
   # Добавьте в crontab (crontab -e)
   0 * * * * cd /path/to/telegram-navigator && docker compose run --rm scheduler >> data/scheduler.log 2>&1
   ```

## Требования

| Параметр | Как получить |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Создайте бота через [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | Зарегистрируйтесь на [my.telegram.org](https://my.telegram.org) |
| `TELEGRAM_SESSION_STRING` | Запустите `make session` локально (интерактивно, нужен телефон + OTP) |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) |
| `ADMIN_TELEGRAM_ID` | Отправьте `/start` боту [@userinfobot](https://t.me/userinfobot) |

> **Важно:** `generate_session.py` нужно запускать локально (не в Docker) — он требует интерактивный ввод номера телефона и кода подтверждения.

## Конфигурация

Все переменные окружения с описаниями — в [`.env.example`](.env.example).

| Переменная | Обязательная | По умолчанию | Описание |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Да | — | Токен Bot API |
| `TELEGRAM_API_ID` | Да | — | Telethon API ID |
| `TELEGRAM_API_HASH` | Да | — | Telethon API hash |
| `TELEGRAM_SESSION_STRING` | Да | — | Строка сессии Telethon |
| `GEMINI_API_KEY` | Да | — | Ключ Google Gemini API |
| `ADMIN_TELEGRAM_ID` | Да | — | Telegram ID администратора |
| `GEMINI_MODEL` | Нет | `gemini-3-flash-preview` | Модель Gemini |
| `DB_BACKEND` | Нет | `sqlite` | `sqlite` или `supabase` |
| `SQLITE_DB_PATH` | Нет | `data/content_table.db` | Путь к SQLite БД |
| `OPENAI_API_KEY` | Нет | — | Включает гибридный векторный поиск |

## Архитектура

```
telegram-navigator/
├── src/
│   ├── main.py              # Точка входа бота (долгоживущий polling)
│   ├── scheduler_main.py    # Часовой cron: fetch → classify → score → TOC → digest
│   ├── bot/                  # Хендлеры, коллбэки, клавиатуры, сообщения (i18n)
│   ├── config/               # Настройки, константы, LLM-промпты
│   ├── database/             # Фабрика БД, модели, SQLite & Supabase запросы
│   ├── services/             # Fetcher, classifier, scorer, TOC generator, digest, embedder
│   └── utils/                # Хелперы, i18n, типы ошибок
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── schema.sql                # Схема Supabase (SQLite создаётся автоматически)
```

**Два процесса:**
1. **Bot** (`src.main`) — Telegram polling, обработка команд и кнопок
2. **Scheduler** (`src.scheduler_main`) — часовой пайплайн: получение постов → классификация → скоринг → обновление TOC → отправка дайджестов

## Деплой

Подробные инструкции — в [docs/deployment.md](docs/deployment.md):
- Docker (рекомендуется)
- Heroku
- VPS / systemd
- Railway / Render / Fly.io

## База данных

Бот поддерживает два бэкенда. Выбор через `DB_BACKEND` в `.env`.

### SQLite (по умолчанию)

Без настройки — база создаётся автоматически при первом запуске в `data/content_table.db`.

```env
DB_BACKEND=sqlite
SQLITE_DB_PATH=data/content_table.db
```

Для гибридного (векторный + ключевые слова) поиска нужно расширение `sqlite-vec` (включено в `requirements.txt`). Без него доступен только поиск по ключевым словам.

### Supabase (PostgreSQL)

Для облачных/продакшн деплоев с постоянным хранилищем.

1. Создайте проект на [supabase.com](https://supabase.com)
2. Перейдите в **SQL Editor** и выполните содержимое [`schema.sql`](schema.sql)
3. Установите переменные окружения:

```env
DB_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
```

Supabase использует pgvector для гибридного поиска — включите расширение `vector` в настройках проекта (Dashboard → Database → Extensions).

## Участие в разработке

См. [CONTRIBUTING.md](CONTRIBUTING.md) — настройка среды разработки, стиль кода и процесс PR.

## Планы

- [ ] Абстракция LLM (Claude, Ollama, OpenRouter)
- [ ] Мультиадмин RBAC
- [ ] Тестовый набор
- [ ] Больше языков (украинский и др.)
- [ ] Язык контента per-channel для TOC и LLM-промптов

## Лицензия

[MIT](LICENSE)
