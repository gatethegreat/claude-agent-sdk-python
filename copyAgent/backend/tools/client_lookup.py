"""
Database client lookup tool.

Queries the database to get distinct client names/slugs from the
documents and approved_copy tables.
"""

from typing import Any
from claude_agent_sdk import tool

# Database dependencies - import lazily
asyncpg = None


async def _get_db_pool():
    """Get or create async database connection pool."""
    global asyncpg

    if asyncpg is None:
        import asyncpg as _asyncpg
        asyncpg = _asyncpg

    from .config import config

    if not config.SUPABASE_DB_URL:
        raise ValueError(
            "Database URL not configured. Set SUPABASE_DB_URL environment variable."
        )

    return await asyncpg.create_pool(config.SUPABASE_DB_URL, min_size=1, max_size=5)


@tool(
    "get_client_names",
    (
        "Get all unique client names/slugs from the knowledge base. "
        "IMPORTANT: ALWAYS call this FIRST before searching. "
        "Use the returned client_slug values when calling company_background_search "
        "or approved_copy_search to ensure correct spelling."
    ),
    {},  # No parameters required
)
async def get_client_names(args: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch all unique client names from the database tables.

    Queries both documents and approved_copy tables to find all distinct
    company_name and client_slug values.
    """
    try:
        from .config import config

        pool = await _get_db_pool()

        async with pool.acquire() as conn:
            # Get distinct company_name from documents table
            docs_query = f"""
                SELECT DISTINCT {config.PGVECTOR_METADATA_COLUMN}->>'company_name' as client
                FROM {config.PGVECTOR_TABLE_NAME}
                WHERE {config.PGVECTOR_METADATA_COLUMN}->>'company_name' IS NOT NULL
            """
            docs_rows = await conn.fetch(docs_query)
            docs_clients = {row['client'] for row in docs_rows if row['client']}

            # Get distinct client_slug and company_name from approved_copy table
            copy_query = f"""
                SELECT DISTINCT
                    {config.PGVECTOR_METADATA_COLUMN}->>'client_slug' as slug,
                    {config.PGVECTOR_METADATA_COLUMN}->>'company_name' as name
                FROM {config.APPROVED_COPY_TABLE_NAME}
                WHERE {config.PGVECTOR_METADATA_COLUMN}->>'client_slug' IS NOT NULL
                   OR {config.PGVECTOR_METADATA_COLUMN}->>'company_name' IS NOT NULL
            """
            copy_rows = await conn.fetch(copy_query)
            copy_clients = set()
            for row in copy_rows:
                if row['slug']:
                    copy_clients.add(row['slug'])
                if row['name']:
                    copy_clients.add(row['name'])

        # Combine all unique clients
        all_clients = sorted(docs_clients | copy_clients)

        if not all_clients:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "No clients found in the database.",
                    }
                ]
            }

        # Format the response
        client_list = "\n".join(f"• {client}" for client in all_clients)
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Available Clients ({len(all_clients)} total):\n\n{client_list}\n\n"
                        "Use these exact values as 'client_name' in company_background_search "
                        "or 'client_slug' in approved_copy_search."
                    ),
                }
            ]
        }

    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error fetching client names: {str(e)}",
                }
            ],
            "is_error": True,
        }
