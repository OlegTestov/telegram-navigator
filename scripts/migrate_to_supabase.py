"""Migrate data from SQLite to Supabase.

Usage:
    python -m scripts.migrate_to_supabase
"""

import os
import sqlite3
import sys

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SQLITE_PATH = os.getenv("SQLITE_DB_PATH", "data/content_table.db")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BATCH_SIZE = 500


def get_sqlite_conn():
    if not os.path.exists(SQLITE_PATH):
        print(f"ERROR: SQLite DB not found at {SQLITE_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def migrate():
    conn = get_sqlite_conn()
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Channels
    rows = conn.execute("SELECT * FROM ct_channels").fetchall()
    print(f"Channels: {len(rows)}")
    for row in rows:
        d = dict(row)
        d["is_active"] = bool(d["is_active"])
        sb.table("ct_channels").insert(d).execute()
    print("  ✓ channels inserted")

    # 2. Posts (batched)
    rows = conn.execute("SELECT * FROM ct_posts").fetchall()
    print(f"Posts: {len(rows)}")
    batch = []
    inserted = 0
    for row in rows:
        d = dict(row)
        d["has_media"] = bool(d["has_media"])
        batch.append(d)
        if len(batch) >= BATCH_SIZE:
            sb.table("ct_posts").insert(batch).execute()
            inserted += len(batch)
            print(f"  {inserted}/{len(rows)}")
            batch = []
    if batch:
        sb.table("ct_posts").insert(batch).execute()
        inserted += len(batch)
    print(f"  ✓ {inserted} posts inserted")

    # 3. Topics
    rows = conn.execute("SELECT * FROM ct_topics").fetchall()
    print(f"Topics: {len(rows)}")
    if rows:
        sb.table("ct_topics").insert([dict(r) for r in rows]).execute()
    print("  ✓ topics inserted")

    # 4. Post-topics (batched)
    rows = conn.execute("SELECT * FROM ct_post_topics").fetchall()
    print(f"Post-topics: {len(rows)}")
    batch = []
    inserted = 0
    for row in rows:
        batch.append(dict(row))
        if len(batch) >= BATCH_SIZE:
            sb.table("ct_post_topics").insert(batch).execute()
            inserted += len(batch)
            print(f"  {inserted}/{len(rows)}")
            batch = []
    if batch:
        sb.table("ct_post_topics").insert(batch).execute()
        inserted += len(batch)
    print(f"  ✓ {inserted} post-topics inserted")

    # 5. User subscriptions
    rows = conn.execute("SELECT * FROM ct_user_subscriptions").fetchall()
    print(f"Subscriptions: {len(rows)}")
    if rows:
        sb.table("ct_user_subscriptions").insert([dict(r) for r in rows]).execute()
    print("  ✓ subscriptions inserted")

    # 6. Verify counts
    print("\n--- Verification ---")
    tables = [
        ("ct_channels", "ct_channels"),
        ("ct_posts", "ct_posts"),
        ("ct_topics", "ct_topics"),
        ("ct_post_topics", "ct_post_topics"),
        ("ct_user_subscriptions", "ct_user_subscriptions"),
    ]
    all_ok = True
    for sqlite_table, sb_table in tables:
        sqlite_count = conn.execute(f"SELECT COUNT(*) FROM {sqlite_table}").fetchone()[0]
        sb_result = sb.table(sb_table).select("*", count="exact", head=True).execute()
        sb_count = sb_result.count
        status = "✓" if sqlite_count == sb_count else "✗"
        if sqlite_count != sb_count:
            all_ok = False
        print(f"  {status} {sqlite_table}: SQLite={sqlite_count}, Supabase={sb_count}")

    if all_ok:
        print("\n✓ Migration complete! All counts match.")
    else:
        print("\n✗ WARNING: Some counts don't match!")

    # 7. Reset sequences (via RPC or manual note)
    print("\n--- Sequence Reset ---")
    print("Run these in Supabase SQL Editor:")
    for table, col in [("ct_channels", "id"), ("ct_posts", "id"), ("ct_topics", "id")]:
        max_id = conn.execute(f"SELECT MAX({col}) FROM {table}").fetchone()[0] or 0
        seq_name = f"{table}_{col}_seq"
        print(f"  SELECT setval('{seq_name}', {max_id});")

    conn.close()


if __name__ == "__main__":
    migrate()
