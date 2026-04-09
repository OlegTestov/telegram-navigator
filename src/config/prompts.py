"""Gemini prompts for post classification, summarization, and translation."""

CLASSIFICATION_PROMPT = """You are a Telegram channel post classifier.

For each post, determine:
1. topics — a list of 1-3 topics (in {language}). Choose from existing topics if they fit. Create a new topic only if none of the existing ones apply.
2. description — a catchy headline up to 50 characters in {language}. Maximum meaning, minimum fluff. Write like a newspaper headline — engaging and to the point.
3. usefulness — a score from 1 to 10, how useful the post is (10 = very useful, practical; 1 = not very useful).

Existing topics:
{existing_topics}

Rules:
- Topics should be general (at least 3 posts should fit).
- Topic name: 1-3 words, noun or noun phrase, in {language}.
- Description: short, concise, no clichés. STRICTLY under 50 characters, in {language}.
- If a post has no useful content (ads, greetings, polls without substance), topic is "{fallback_topic}".

Respond strictly in JSON:
[
  {{
    "post_index": 0,
    "topics": ["Productivity", "Habits"],
    "description": "The 1-3-5 method for daily planning",
    "usefulness": 8
  }}
]

Posts to classify:
{posts}"""

TOPIC_SUMMARY_PROMPT = """Write a brief summary (2-3 sentences) in {language} for the topic "{topic_name}" \
based on post descriptions.

Post descriptions:
{post_descriptions}

The summary should give a general idea of what this topic is about in the channel. \
Don't list posts, generalize."""

TOC_GROUPING_PROMPT = """You are a Telegram channel content organizer. \
You are given posts with descriptions, IDs, and tags (in square brackets).

Task: divide ALL posts into exactly {groups_count} non-overlapping thematic groups.

Rules:
- Each post must go into exactly ONE group.
- Groups should be roughly equal in size (±30%).
- Group name: 2-4 words in {language}, concisely reflecting the content.
- Groups should not overlap in meaning.
- Posts with common tags are likely related — try to keep them in one group.
- Posts without useful content (ads, greetings) go into the least suitable group, don't create a separate one.

Respond strictly in JSON:
[
  {{
    "group_name": "Group Name",
    "post_ids": [74, 102, 81, ...]
  }},
  ...
]

Posts:
{posts}"""

TRANSLATION_PROMPT = """Translate each text to {target_lang}.
Keep the same style and approximate length.
Do NOT translate proper nouns, brand names, tool names, or channel names (e.g. @channelname).
Return exactly {count} translations as a numbered list (1. ... 2. ... etc).

{texts}"""

# Language-specific fallback values
LANGUAGE_FALLBACK = {
    "ru": {"fallback_topic": "Прочее", "fallback_group": "Группа", "name": "Russian"},
    "en": {"fallback_topic": "Other", "fallback_group": "Group", "name": "English"},
    "es": {"fallback_topic": "Otros", "fallback_group": "Grupo", "name": "Spanish"},
    "de": {"fallback_topic": "Sonstiges", "fallback_group": "Gruppe", "name": "German"},
    "fr": {"fallback_topic": "Autres", "fallback_group": "Groupe", "name": "French"},
}


def get_language_config(lang: str) -> dict:
    """Get language-specific config. Falls back to English-like defaults."""
    return LANGUAGE_FALLBACK.get(lang, {"fallback_topic": "Other", "fallback_group": "Group", "name": lang.title()})


def get_language_name(lang: str) -> str:
    """Get human-readable language name for prompts."""
    return get_language_config(lang)["name"]
