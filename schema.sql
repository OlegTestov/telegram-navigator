-- content-table: Telegram Channel TOC Bot
-- Run this in Supabase SQL Editor or via psql

CREATE TABLE ct_channels (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    title TEXT,
    added_by BIGINT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    pinned_message_id INTEGER,
    pinned_chat_id BIGINT,
    pinned_content_hash TEXT,
    peer_id BIGINT,
    last_fetched_message_id INTEGER DEFAULT 0,
    last_run_at TIMESTAMPTZ,
    total_posts_indexed INTEGER DEFAULT 0,
    cached_toc TEXT,
    toc_updated_at TIMESTAMPTZ,
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
CREATE INDEX idx_ct_posts_channel_date ON ct_posts(channel_id, post_date DESC);

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

CREATE TABLE ct_user_subscriptions (
    user_id BIGINT NOT NULL,
    channel_id INTEGER NOT NULL REFERENCES ct_channels(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, channel_id)
);

CREATE TABLE ct_channel_digests (
    id BIGSERIAL PRIMARY KEY,
    channel_id INTEGER NOT NULL REFERENCES ct_channels(id) ON DELETE CASCADE,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    content TEXT NOT NULL,
    post_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(channel_id, period_start)
);
CREATE INDEX idx_ct_channel_digests_period ON ct_channel_digests(period_end DESC);

CREATE TABLE ct_digest_deliveries (
    user_id BIGINT NOT NULL,
    digest_id BIGINT NOT NULL REFERENCES ct_channel_digests(id) ON DELETE CASCADE,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, digest_id)
);
