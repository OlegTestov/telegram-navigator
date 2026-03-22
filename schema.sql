-- content-table: Telegram Channel TOC Bot
-- Run this in Supabase SQL Editor

CREATE TABLE ct_channels (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    title TEXT,
    added_by BIGINT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    -- pinned post editing (optional)
    pinned_message_id INTEGER,
    pinned_chat_id BIGINT,
    pinned_content_hash TEXT,
    -- sync state
    last_fetched_message_id INTEGER DEFAULT 0,
    last_run_at TIMESTAMPTZ,
    total_posts_indexed INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ct_posts (
    id BIGSERIAL PRIMARY KEY,
    channel_id INTEGER NOT NULL REFERENCES ct_channels(id) ON DELETE CASCADE,
    message_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    description TEXT,
    post_date TIMESTAMPTZ NOT NULL,
    post_url TEXT NOT NULL,
    has_media BOOLEAN DEFAULT FALSE,
    views INTEGER DEFAULT 0,
    forwards INTEGER DEFAULT 0,
    reactions_count INTEGER DEFAULT 0,
    usefulness_score FLOAT DEFAULT 0.5,
    score FLOAT DEFAULT 0,
    classified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(channel_id, message_id)
);
CREATE INDEX idx_ct_posts_channel ON ct_posts(channel_id);
CREATE INDEX idx_ct_posts_score ON ct_posts(channel_id, score DESC);
CREATE INDEX idx_ct_posts_unclassified ON ct_posts(channel_id) WHERE classified_at IS NULL;

CREATE TABLE ct_topics (
    id SERIAL PRIMARY KEY,
    channel_id INTEGER NOT NULL REFERENCES ct_channels(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    emoji TEXT DEFAULT '',
    summary TEXT,
    post_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(channel_id, slug)
);
CREATE INDEX idx_ct_topics_channel ON ct_topics(channel_id);

CREATE TABLE ct_post_topics (
    post_id BIGINT REFERENCES ct_posts(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES ct_topics(id) ON DELETE CASCADE,
    PRIMARY KEY (post_id, topic_id)
);
CREATE INDEX idx_ct_post_topics_topic ON ct_post_topics(topic_id);
