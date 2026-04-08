"""Russian UI strings."""

# --- Start & Help ---

WELCOME_ADMIN = (
    "\U0001f44b <b>Привет! Я — бот-навигатор по Telegram-каналам.</b>\n\n"
    "Я слежу за Telegram-каналами и помогаю:\n"
    "\U0001f50d <b>Поиск</b> — найти пост по словам\n"
    "\U0001f4ec <b>Подписки</b> — получать сводку новых постов\n"
    "\U0001f4e2 <b>Каналы</b> — посмотреть отслеживаемые каналы\n"
    "➕ <b>Добавить канал</b> — начать отслеживать новый канал"
)

WELCOME_USER = (
    "\U0001f44b <b>Привет! Я — бот-навигатор по Telegram-каналам.</b>\n\n"
    "Я слежу за Telegram-каналами и помогаю:\n"
    "\U0001f50d <b>Поиск</b> — найти пост по словам\n"
    "\U0001f4ec <b>Подписки</b> — получать сводку новых постов\n"
    "\U0001f4e2 <b>Каналы</b> — посмотреть отслеживаемые каналы\n"
    "\U0001f4e8 <b>Предложить канал</b> — предложить канал для добавления"
)

HELP_ADMIN = (
    "\U0001f4d6 <b>Что я умею:</b>\n\n"
    "<b>Для всех:</b>\n"
    "\U0001f4e2 Каналы — оглавление, темы, поиск внутри канала\n"
    "\U0001f50d Поиск — умный поиск по всем каналам сразу\n"
    "\U0001f4ec Подписки — дайджест новых постов каждые 3 часа\n\n"
    "<b>Для админа:</b>\n"
    "➕ Отправьте ссылку — канал будет добавлен\n"
    "⚙️ Настройки канала — пиннед-пост, удаление\n"
    "\U0001f4ca /stats — статистика\n\n"
    "<b>Команды:</b>\n"
    "/channels · /search · /stats · /help"
)

HELP_USER = (
    "\U0001f4d6 <b>Что я умею:</b>\n\n"
    "\U0001f4e2 <b>Каналы</b> — оглавление, темы, поиск внутри канала\n"
    "\U0001f50d <b>Поиск</b> — умный поиск по всем каналам сразу\n"
    "\U0001f4ec <b>Подписки</b> — дайджест новых постов каждые 3 часа\n"
    "\U0001f4e8 <b>Предложить канал</b> — отправьте ссылку, и я передам админу\n\n"
    "<b>Команды:</b>\n"
    "/channels · /search · /help"
)

# --- Access ---

NOT_ADMIN = "⛔ Эта функция доступна только администратору."

# --- Channels ---

CHANNEL_ADDED = "✅ Канал @{username} добавлен!\nИндексация начнётся в течение часа."
CHANNEL_EXISTS = "ℹ️ Канал @{username} уже отслеживается."
CHANNEL_SUGGESTED = "\U0001f4e8 Спасибо! Заявка на добавление @{username} отправлена администратору."
CHANNEL_SUGGESTION_NOTIFY = (
    "\U0001f4e8 <b>Заявка на канал</b>\n\n"
    "Пользователь: {user_name} (id: <code>{user_id}</code>)\n"
    "Канал: @{username}\n\n"
    "Чтобы добавить, отправьте боту: t.me/{username}"
)
CHANNEL_NOT_FOUND = "❌ Канал не найден. Проверьте ссылку."
CHANNELS_HEADER = "\U0001f4e2 <b>Каналы</b>\n<i>Выберите канал, чтобы посмотреть оглавление и темы.</i>"
INVALID_LINK = "Не удалось распознать ссылку.\nОтправьте в формате t.me/channelname"
NO_CHANNELS = "\U0001f4ed Пока нет добавленных каналов."
ADD_CHANNEL_PROMPT = "➕ <b>Добавить канал</b>\n\nОтправьте ссылку на канал, например:\n<code>t.me/channelname</code>"
SUGGEST_CHANNEL_PROMPT = (
    "\U0001f4e8 <b>Предложить канал</b>\n\n"
    "Отправьте ссылку на канал, например:\n"
    "<code>t.me/channelname</code>\n\n"
    "Администратор рассмотрит заявку."
)

# --- Channel info ---

CHANNEL_INFO = "\U0001f4e2 <b>@{username}</b>\n\nПостов: {post_count}\nТем: {topic_count}\n\n{status}"
CHANNEL_STATUS_NOT_INDEXED = "⏳ Индексация ещё не запускалась."
CHANNEL_STATUS_NO_TOC = "Нажмите «Создать оглавление» для генерации."
CHANNEL_STATUS_TOC_FRESH = "<i>Оглавление актуально, новых постов нет.</i>"
CHANNEL_ERROR = "❌ Канал не найден."

# --- TOC ---

TOC_GENERATING = "⏳ Генерирую оглавление — это может занять около минуты..."
TOC_EMPTY = "\U0001f4da Оглавление @{username}\n\nПока нет проиндексированных постов."

# --- Topics ---

TOPICS_HEADER = "\U0001f4cb <b>Темы</b>\n<i>Выберите тему, чтобы посмотреть посты.</i>"
NO_TOPICS = "\U0001f4ed Тем пока нет. Дождитесь индексации канала."
TOPIC_NOT_FOUND = "❌ Тема не найдена."

# --- Search ---

SEARCH_PROMPT_GLOBAL = "\U0001f50d <b>Поиск</b>\n\nВведите слово или фразу — я найду подходящие посты\nпо всем каналам."
SEARCH_PROMPT_CHANNEL = "\U0001f50d <b>Поиск по каналу</b>\n\nВведите слово или фразу:"
SEARCH_NO_RESULTS = "\U0001f50d По запросу «{query}» ничего не найдено.\nПопробуйте другие ключевые слова."
SEARCH_RESULTS_HEADER = "\U0001f50d Результаты по «{query}»:"

# --- Settings (admin) ---

SETTINGS_INFO = "⚙️ <b>Настройки @{username}</b>\n\nПостов: {total_posts}\nПоследний запуск: {last_run}"
PINNED_SET = "✅ Буду обновлять пост #{message_id} в @{username}.\nОглавление будет обновляться раз в час."
PINNED_PROMPT = (
    "\U0001f4cc Отправьте ссылку на пост в @{username}, "
    "который я буду обновлять.\n"
    "Например: t.me/{username}/123\n\n"
    "Убедитесь, что бот добавлен админом канала."
)
PINNED_CLEARED = "✅ Пиннед-пост отключён."
PINNED_WRONG_CHANNEL = "❌ Этот пост не из отслеживаемого канала."
PINNED_ACCESS_ERROR = "❌ Не удалось получить доступ к каналу. Убедитесь, что бот добавлен админом."
FORCE_UPDATE_INFO = (
    "\U0001f504 Запустите вручную:\n"
    "<code>python -m src.scheduler_main</code>\n\n"
    "Или дождитесь следующего часового обновления."
)
CHANNEL_DELETED = "\U0001f5d1 Канал @{username} удалён вместе со всеми данными."

# --- Subscriptions ---

SUBSCRIBED = "✅ Вы подписались на дайджест @{username}.\nДайджест приходит каждые 3 часа."
UNSUBSCRIBED = "\U0001f4ed Вы отписались от дайджеста @{username}."
SUBS_HEADER = (
    "\U0001f4ec <b>Подписки на дайджест</b>\n\n"
    "✅ — вы подписаны, ◻️ — нет.\n"
    "Нажмите на канал, чтобы переключить.\n\n"
    "<i>Дайджест приходит каждые 3 часа\n"
    "со сводкой новых постов.</i>"
)
SUBS_EMPTY = (
    "\U0001f4ec <b>Подписки на дайджест</b>\n\n"
    "Пока нет каналов для подписки.\n"
    "Дождитесь, пока администратор добавит каналы."
)
DIGEST_HEADER = "\U0001f4ec <b>Дайджест</b> ({period})"
DIGEST_MORE_POSTS = "  ...и ещё {count} постов"

# --- Stats ---

STATS_TEMPLATE = "\U0001f4ca <b>Статистика:</b>\n\nКаналов: {channels}\nПостов: {total_posts}\nТем: {total_topics}"

# --- Language ---

CHOOSE_LANGUAGE = "\U0001f310 Choose your language / Выберите язык:"

# --- Keyboard labels ---

KB_SEARCH = "\U0001f50d Поиск"
KB_BACK = "\U0001f519 Назад"
KB_CHANNELS = "\U0001f4e2 Каналы"
KB_SUBSCRIPTIONS = "\U0001f4ec Подписки"
KB_ADD_CHANNEL = "➕ Добавить канал"
KB_SUGGEST = "\U0001f4e8 Предложить канал"
KB_REFRESH_TOC = "\U0001f504 Обновить оглавление"
KB_CREATE_TOC = "\U0001f4da Создать оглавление"
KB_ALL_TOPICS = "\U0001f4cb Все темы"
KB_SUBSCRIBE = "\U0001f4ec Подписаться"
KB_UNSUBSCRIBE = "\U0001f4ed Отписаться"
KB_SETTINGS = "⚙️ Настройки"
KB_TO_CHANNEL = "\U0001f519 К каналу"
KB_TO_TOPICS = "\U0001f519 К темам"
KB_NEW_SEARCH = "\U0001f50d Новый поиск"
KB_LANGUAGE = "\U0001f310 Язык"
KB_SET_PINNED = "\U0001f4cc Настроить пиннед-пост"
KB_PINNED_STATUS = "\U0001f4cc Пиннед: пост #{id}"
KB_FORCE_UPDATE = "\U0001f504 Обновить сейчас"
KB_DELETE_CHANNEL = "\U0001f5d1 Удалить канал"
KB_OPEN_MENU = "\U0001f4cb Открыть меню"
