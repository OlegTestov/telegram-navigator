"""Apply schema.sql to Supabase via the REST SQL endpoint.

Usage:
    python -m scripts.apply_schema
"""

import importlib.util
import os

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def apply_schema():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    with open(schema_path) as f:
        sql = f.read()

    # Extract project ref from URL
    # https://your-project-ref.supabase.co -> your-project-ref
    project_ref = SUPABASE_URL.replace("https://", "").split(".")[0]

    print("Supabase doesn't expose raw SQL execution via REST API.")
    print("Please apply the schema using one of these methods:\n")
    print("Option 1: Supabase SQL Editor (Dashboard)")
    print(f"  Open: https://supabase.com/dashboard/project/{project_ref}/sql/new")
    print("  Paste contents of schema.sql and click 'Run'\n")
    print("Option 2: Install psql and run:")
    print("  brew install libpq && brew link --force libpq")
    print(
        f"  psql 'postgresql://postgres.{project_ref}:PASSWORD@aws-0-eu-central-1.pooler.supabase.com:6543/postgres' -f schema.sql\n"
    )
    print("Option 3: Install psycopg2 and run this script with --psycopg2 flag")

    # Check if psycopg2 is available
    if importlib.util.find_spec("psycopg2"):
        print("\npsycopg2 found! But we need the database password.")
        print("Set DATABASE_URL in .env and re-run with --direct flag.")

    print(f"\nSchema SQL ({len(sql)} chars) is ready in schema.sql")


if __name__ == "__main__":
    apply_schema()
