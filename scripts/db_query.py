#!/usr/bin/env python3
"""
Utility script to query pgvector database directly.

Usage:
    python scripts/db_query.py schema          # Show table schema
    python scripts/db_query.py list            # List all documents
    python scripts/db_query.py search "query"  # Semantic search
    python scripts/db_query.py clients         # List unique clients
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from dotenv import load_dotenv

# Load env from copyAgent or chatApp
for env_path in [
    Path(__file__).parent.parent / "copyAgent/backend/.env",
    Path(__file__).parent.parent / "chatApp/backend/.env",
]:
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded: {env_path}")
        break

DB_URL = os.getenv("SUPABASE_DB_URL")
TABLE_NAME = os.getenv("PGVECTOR_TABLE_NAME", "documents")
APPROVED_COPY_TABLE = os.getenv("APPROVED_COPY_TABLE_NAME", "approved_copy")


async def get_conn():
    if not DB_URL:
        print("Error: SUPABASE_DB_URL not set")
        sys.exit(1)
    return await asyncpg.connect(DB_URL)


async def show_schema():
    """Show pgvector table schema."""
    conn = await get_conn()

    # List all tables
    tables = await conn.fetch("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)

    print("\n=== TABLES ===")
    for t in tables:
        print(f"  - {t['table_name']}")

    # Show columns for main tables
    for table in [TABLE_NAME, APPROVED_COPY_TABLE]:
        cols = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = $1
            ORDER BY ordinal_position
        """, table)

        if cols:
            print(f"\n=== {table.upper()} COLUMNS ===")
            for c in cols:
                nullable = "NULL" if c['is_nullable'] == 'YES' else "NOT NULL"
                print(f"  {c['column_name']}: {c['data_type']} ({nullable})")

    await conn.close()


async def list_documents(limit: int = 20):
    """List documents in the vector store."""
    conn = await get_conn()

    # Check if table exists
    exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = $1
        )
    """, TABLE_NAME)

    if not exists:
        print(f"Table '{TABLE_NAME}' does not exist")
        await conn.close()
        return

    # Get count
    count = await conn.fetchval(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    print(f"\n=== {TABLE_NAME} ({count} total rows) ===\n")

    # Get sample rows (without embedding column - too large)
    rows = await conn.fetch(f"""
        SELECT id, content, metadata
        FROM {TABLE_NAME}
        LIMIT $1
    """, limit)

    for i, row in enumerate(rows, 1):
        content_preview = str(row['content'])[:100] + "..." if len(str(row['content'])) > 100 else row['content']
        print(f"{i}. [ID: {row.get('id', 'N/A')}]")
        print(f"   Content: {content_preview}")
        print(f"   Metadata: {row['metadata']}")
        print()

    await conn.close()


async def list_clients():
    """List unique clients in the vector store."""
    conn = await get_conn()

    # Try to get unique company names from metadata
    try:
        clients = await conn.fetch(f"""
            SELECT DISTINCT metadata->>'company_name' as client
            FROM {TABLE_NAME}
            WHERE metadata->>'company_name' IS NOT NULL
            ORDER BY client
        """)

        print(f"\n=== CLIENTS IN {TABLE_NAME} ===")
        if clients:
            for c in clients:
                print(f"  - {c['client']}")
        else:
            print("  No clients found (metadata->>'company_name' is empty)")

    except Exception as e:
        print(f"Error: {e}")

    await conn.close()


async def semantic_search(query: str, top_k: int = 5):
    """Semantic search using OpenAI embeddings."""
    from openai import OpenAI

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("Error: OPENAI_API_KEY not set")
        return

    client = OpenAI(api_key=openai_key)

    # Get embedding
    print(f"Getting embedding for: '{query}'")
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query,
    )
    embedding = response.data[0].embedding

    # Search
    conn = await get_conn()
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    rows = await conn.fetch(f"""
        SELECT
            content,
            metadata,
            1 - (embedding <=> $1::vector) as similarity
        FROM {TABLE_NAME}
        ORDER BY embedding <=> $1::vector
        LIMIT $2
    """, embedding_str, top_k)

    print(f"\n=== SEARCH RESULTS ({len(rows)} matches) ===\n")
    for i, row in enumerate(rows, 1):
        sim = row['similarity'] * 100
        content_preview = str(row['content'])[:200] + "..." if len(str(row['content'])) > 200 else row['content']
        print(f"{i}. [{sim:.1f}% match]")
        print(f"   {content_preview}")
        print(f"   Metadata: {row['metadata']}")
        print()

    await conn.close()


async def list_approved_copy(limit: int = 20):
    """List approved copy entries."""
    conn = await get_conn()

    exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = $1
        )
    """, APPROVED_COPY_TABLE)

    if not exists:
        print(f"Table '{APPROVED_COPY_TABLE}' does not exist")
        await conn.close()
        return

    count = await conn.fetchval(f"SELECT COUNT(*) FROM {APPROVED_COPY_TABLE}")
    print(f"\n=== {APPROVED_COPY_TABLE} ({count} total rows) ===\n")

    # Get columns first
    cols = await conn.fetch("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = $1
        ORDER BY ordinal_position
    """, APPROVED_COPY_TABLE)

    col_names = [c['column_name'] for c in cols if c['column_name'] != 'embedding']

    rows = await conn.fetch(f"""
        SELECT {', '.join(col_names)}
        FROM {APPROVED_COPY_TABLE}
        LIMIT $1
    """, limit)

    for i, row in enumerate(rows, 1):
        print(f"{i}. {dict(row)}")
        print()

    await conn.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "schema":
        asyncio.run(show_schema())
    elif cmd == "list":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        asyncio.run(list_documents(limit))
    elif cmd == "clients":
        asyncio.run(list_clients())
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: python db_query.py search 'your query'")
            sys.exit(1)
        asyncio.run(semantic_search(sys.argv[2]))
    elif cmd == "approved":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        asyncio.run(list_approved_copy(limit))
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
