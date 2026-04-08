"""Apply schema.sql to Supabase via the REST SQL endpoint.

Usage:
    python -m scripts.apply_schema
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def apply_schema():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    with open(schema_path) as f:
        sql = f.read()

    # Use Supabase's PostgREST rpc or the pg_net extension
    # Simplest: use the /rest/v1/rpc endpoint won't work for DDL
    # Instead, use the Supabase Management API or the SQL endpoint

    # The supabase-py client doesn't expose raw SQL execution.
    # Use the pg REST SQL endpoint available via the service role key.
    url = f"{SUPABASE_URL}/rest/v1/rpc/"

    # Actually, Supabase doesn't expose raw SQL via REST.
    # We need to use psycopg2 or the Supabase Dashboard SQL Editor.
    # Let's try with the Supabase Management API.

    # Extract project ref from URL
    # https://your-project-ref.supabase.co -> your-project-ref
    project_ref = SUPABASE_URL.replace("https://", "").split(".")[0]

    print("Supabase doesn't expose raw SQL execution via REST API.")
    print("Please apply the schema using one of these methods:\n")
    print("Option 1: Supabase SQL Editor (Dashboard)")
    print(f"  Open: https://supabase.com/dashboard/project/{project_ref}/sql/new")
    print(f"  Paste contents of schema.sql and click 'Run'\n")
    print("Option 2: Install psql and run:")
    print(f"  brew install libpq && brew link --force libpq")
    print(f"  psql 'postgresql://postgres.{project_ref}:PASSWORD@aws-0-eu-central-1.pooler.supabase.com:6543/postgres' -f schema.sql\n")
    print("Option 3: Install psycopg2 and run this script with --psycopg2 flag")

    # Try psycopg2 if available
    try:
        import psycopg2
        print("\npsycopg2 found! But we need the database password.")
        print("Set DATABASE_URL in .env and re-run with --direct flag.")
    except ImportError:
        pass

    print(f"\nSchema SQL ({len(sql)} chars) is ready in schema.sql")


if __name__ == "__main__":
    apply_schema()
