"""English UI strings."""

# --- Start & Help ---

WELCOME_ADMIN = (
    "\U0001f44b <b>Hi! I'm a Telegram channel navigator bot.</b>\n\n"
    "I monitor Telegram channels and help you:\n"
    "\U0001f50d <b>Search</b> — find posts by keywords\n"
    "\U0001f4ec <b>Subscriptions</b> — get digests of new posts\n"
    "\U0001f4e2 <b>Channels</b> — browse tracked channels\n"
    "➕ <b>Add channel</b> — start tracking a new channel"
)

WELCOME_USER = (
    "\U0001f44b <b>Hi! I'm a Telegram channel navigator bot.</b>\n\n"
    "I monitor Telegram channels and help you:\n"
    "\U0001f50d <b>Search</b> — find posts by keywords\n"
    "\U0001f4ec <b>Subscriptions</b> — get digests of new posts\n"
    "\U0001f4e2 <b>Channels</b> — browse tracked channels\n"
    "\U0001f4e8 <b>Suggest channel</b> — suggest a channel to add"
)

HELP_ADMIN = (
    "\U0001f4d6 <b>What I can do:</b>\n\n"
    "<b>For everyone:</b>\n"
    "\U0001f4e2 Channels — table of contents, topics, in-channel search\n"
    "\U0001f50d Search — smart search across all channels\n"
    "\U0001f4ec Subscriptions — digest of new posts every 3 hours\n\n"
    "<b>For admin:</b>\n"
    "➕ Send a link — channel will be added\n"
    "⚙️ Channel settings — pinned post, deletion\n"
    "\U0001f4ca /stats — statistics\n\n"
    "<b>Commands:</b>\n"
    "/channels · /search · /stats · /help"
)

HELP_USER = (
    "\U0001f4d6 <b>What I can do:</b>\n\n"
    "\U0001f4e2 <b>Channels</b> — table of contents, topics, in-channel search\n"
    "\U0001f50d <b>Search</b> — smart search across all channels\n"
    "\U0001f4ec <b>Subscriptions</b> — digest of new posts every 3 hours\n"
    "\U0001f4e8 <b>Suggest channel</b> — send a link and I'll forward it to the admin\n\n"
    "<b>Commands:</b>\n"
    "/channels · /search · /help"
)

# --- Access ---

NOT_ADMIN = "⛔ This feature is available to the admin only."

# --- Channels ---

CHANNEL_ADDED = "✅ Channel @{username} added!\nIndexing will start within an hour."
CHANNEL_EXISTS = "ℹ️ Channel @{username} is already being tracked."
CHANNEL_SUGGESTED = "\U0001f4e8 Thank you! A request to add @{username} has been sent to the admin."
CHANNEL_SUGGESTION_NOTIFY = (
    "\U0001f4e8 <b>Channel suggestion</b>\n\n"
    "User: {user_name} (id: <code>{user_id}</code>)\n"
    "Channel: @{username}\n\n"
    "To add, send the bot: t.me/{username}"
)
CHANNEL_NOT_FOUND = "❌ Channel not found. Check the link."
CHANNELS_HEADER = "\U0001f4e2 <b>Channels</b>\n<i>Select a channel to view its table of contents and topics.</i>"
INVALID_LINK = "Could not recognize the link.\nSend in the format t.me/channelname"
NO_CHANNELS = "\U0001f4ed No channels added yet."
ADD_CHANNEL_PROMPT = "➕ <b>Add channel</b>\n\nSend a channel link, for example:\n<code>t.me/channelname</code>"
SUGGEST_CHANNEL_PROMPT = (
    "\U0001f4e8 <b>Suggest channel</b>\n\n"
    "Send a channel link, for example:\n"
    "<code>t.me/channelname</code>\n\n"
    "The admin will review your suggestion."
)

# --- Channel info ---

CHANNEL_INFO = "\U0001f4e2 <b>@{username}</b>\n\nPosts: {post_count}\nTopics: {topic_count}\n\n{status}"
CHANNEL_STATUS_NOT_INDEXED = "⏳ Indexing has not started yet."
CHANNEL_STATUS_NO_TOC = 'Press "Generate TOC" to create a table of contents.'
CHANNEL_STATUS_TOC_FRESH = "<i>Table of contents is up to date, no new posts.</i>"
CHANNEL_ERROR = "❌ Channel not found."

# --- TOC ---

TOC_GENERATING = "⏳ Generating table of contents — this may take about a minute..."
TOC_EMPTY = "\U0001f4da Table of contents @{username}\n\nNo indexed posts yet."

# --- Topics ---

TOPICS_HEADER = "\U0001f4cb <b>Topics</b>\n<i>Select a topic to view its posts.</i>"
NO_TOPICS = "\U0001f4ed No topics yet. Wait for channel indexing."
TOPIC_NOT_FOUND = "❌ Topic not found."

# --- Search ---

SEARCH_PROMPT_GLOBAL = (
    "\U0001f50d <b>Search</b>\n\nEnter a word or phrase — I'll find matching posts\nacross all channels."
)
SEARCH_PROMPT_CHANNEL = "\U0001f50d <b>Search in channel</b>\n\nEnter a word or phrase:"
SEARCH_NO_RESULTS = '\U0001f50d No results for "{query}".\nTry different keywords.'
SEARCH_RESULTS_HEADER = '\U0001f50d Results for "{query}":'

# --- Settings (admin) ---

SETTINGS_INFO = "⚙️ <b>Settings @{username}</b>\n\nPosts: {total_posts}\nLast run: {last_run}"
PINNED_SET = "✅ I will update post #{message_id} in @{username}.\nThe table of contents will be refreshed every hour."
PINNED_PROMPT = (
    "\U0001f4cc Send a link to a post in @{username} "
    "that I should keep updated.\n"
    "For example: t.me/{username}/123\n\n"
    "Make sure the bot is added as a channel admin."
)
PINNED_CLEARED = "✅ Pinned post disabled."
PINNED_WRONG_CHANNEL = "❌ This post is not from a tracked channel."
PINNED_ACCESS_ERROR = "❌ Could not access the channel. Make sure the bot is added as an admin."
FORCE_UPDATE_INFO = (
    "\U0001f504 Run manually:\n<code>python -m src.scheduler_main</code>\n\nOr wait for the next hourly update."
)
CHANNEL_DELETED = "\U0001f5d1 Channel @{username} deleted with all its data."

# --- Subscriptions ---

SUBSCRIBED = "✅ You subscribed to @{username} digest.\nDigest is sent every 3 hours."
UNSUBSCRIBED = "\U0001f4ed You unsubscribed from @{username} digest."
SUBS_HEADER = (
    "\U0001f4ec <b>Digest subscriptions</b>\n\n"
    "✅ — subscribed, ◻️ — not.\n"
    "Tap a channel to toggle.\n\n"
    "<i>Digest is sent every 3 hours\n"
    "with a summary of new posts.</i>"
)
SUBS_EMPTY = "\U0001f4ec <b>Digest subscriptions</b>\n\nNo channels available yet.\nWait for the admin to add channels."
DIGEST_HEADER = "\U0001f4ec <b>Digest</b> ({period})"
DIGEST_MORE_POSTS = "  ...and {count} more posts"

# --- Stats ---

STATS_TEMPLATE = "\U0001f4ca <b>Statistics:</b>\n\nChannels: {channels}\nPosts: {total_posts}\nTopics: {total_topics}"

# --- Language ---

CHOOSE_LANGUAGE = "\U0001f310 Choose your language / Выберите язык:"

# --- Keyboard labels ---

KB_SEARCH = "\U0001f50d Search"
KB_BACK = "\U0001f519 Back"
KB_CHANNELS = "\U0001f4e2 Channels"
KB_SUBSCRIPTIONS = "\U0001f4ec Subscriptions"
KB_ADD_CHANNEL = "➕ Add channel"
KB_SUGGEST = "\U0001f4e8 Suggest channel"
KB_REFRESH_TOC = "\U0001f504 Refresh TOC"
KB_CREATE_TOC = "\U0001f4da Generate TOC"
KB_ALL_TOPICS = "\U0001f4cb All topics"
KB_SUBSCRIBE = "\U0001f4ec Subscribe"
KB_UNSUBSCRIBE = "\U0001f4ed Unsubscribe"
KB_SETTINGS = "⚙️ Settings"
KB_TO_CHANNEL = "\U0001f519 To channel"
KB_TO_TOPICS = "\U0001f519 To topics"
KB_NEW_SEARCH = "\U0001f50d New search"
KB_LANGUAGE = "\U0001f310 Language"
KB_SET_PINNED = "\U0001f4cc Set pinned post"
KB_PINNED_STATUS = "\U0001f4cc Pinned: post #{id}"
KB_FORCE_UPDATE = "\U0001f504 Update now"
KB_DELETE_CHANNEL = "\U0001f5d1 Delete channel"
KB_OPEN_MENU = "\U0001f4cb Open menu"
