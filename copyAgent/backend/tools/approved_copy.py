"""
Approved copy search tool.

Performs semantic search on the approved_copy table to retrieve
examples of previously approved marketing copy for reference.
"""

from typing import Any
from claude_agent_sdk import tool

# Database dependencies - import lazily
asyncpg = None
openai_client = None


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


def _get_openai_client():
    """Get OpenAI client for embeddings."""
    global openai_client

    if openai_client is None:
        from openai import OpenAI

        from .config import config

        if not config.OPENAI_API_KEY:
            raise ValueError(
                "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
            )

        openai_client = OpenAI(api_key=config.OPENAI_API_KEY)

    return openai_client


async def _get_embedding(text: str) -> list[float]:
    """Generate embedding for text using OpenAI."""
    client = _get_openai_client()

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )

    return response.data[0].embedding


async def _search_approved_copy(
    query_embedding: list[float],
    client_slug: str | None = None,
    email_type: str | None = None,
    content_type: str | None = None,
    top_k: int = 6,
) -> list[dict]:
    """Search approved_copy table for similar examples."""
    from .config import config

    pool = await _get_db_pool()

    # Build WHERE clause dynamically
    conditions = []
    params = []
    param_idx = 1

    # Embedding is always first param
    params.append(None)  # placeholder for embedding string
    param_idx += 1

    if client_slug:
        conditions.append(
            f"({config.PGVECTOR_METADATA_COLUMN}->>'client_slug' = ${param_idx} "
            f"OR {config.PGVECTOR_METADATA_COLUMN}->>'company_name' = ${param_idx})"
        )
        params.append(client_slug)
        param_idx += 1

    if email_type:
        conditions.append(f"{config.PGVECTOR_METADATA_COLUMN}->>'email_type' = ${param_idx}")
        params.append(email_type)
        param_idx += 1

    if content_type:
        conditions.append(f"{config.PGVECTOR_METADATA_COLUMN}->>'content_type' = ${param_idx}")
        params.append(content_type)
        param_idx += 1

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT
            {config.PGVECTOR_CONTENT_COLUMN},
            {config.PGVECTOR_METADATA_COLUMN},
            1 - ({config.PGVECTOR_EMBEDDING_COLUMN} <=> $1::vector) as similarity
        FROM {config.APPROVED_COPY_TABLE_NAME}
        {where_clause}
        ORDER BY {config.PGVECTOR_EMBEDDING_COLUMN} <=> $1::vector
        LIMIT ${param_idx}
    """
    params.append(top_k)

    async with pool.acquire() as conn:
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        params[0] = embedding_str
        rows = await conn.fetch(query, *params)

        results = []
        for row in rows:
            results.append(
                {
                    "content": row[config.PGVECTOR_CONTENT_COLUMN],
                    "metadata": row[config.PGVECTOR_METADATA_COLUMN],
                    "similarity": float(row["similarity"]),
                }
            )

        return results


@tool(
    "approved_copy_search",
    (
        "Search for examples of previously approved marketing copy. "
        "Use this to find reference examples that match the style and tone "
        "the client has approved before. IMPORTANT: Use get_client_names first "
        "to get the correct client_slug. Returns up to 6 most relevant examples."
    ),
    {
        "query": str,  # The search query (e.g., 'email subject lines', 'product descriptions')
        "client_slug": str,  # Optional: client name/slug from get_client_names
        "email_type": str,  # Optional: filter by email type (e.g., 'sale', 'black-friday')
        "content_type": str,  # Optional: filter by content type (e.g., 'full_email')
    },
)
async def approved_copy_search(args: dict[str, Any]) -> dict[str, Any]:
    """Search approved copy database using semantic similarity."""
    query = args.get("query", "").strip()
    client_slug = args.get("client_slug", "").strip() or None
    email_type = args.get("email_type", "").strip() or None
    content_type = args.get("content_type", "").strip() or None

    if not query:
        return {
            "content": [{"type": "text", "text": "Error: query is required."}],
            "is_error": True,
        }

    try:
        from .config import config

        if not config.validate_pgvector():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Error: Database credentials not configured.",
                    }
                ],
                "is_error": True,
            }

        query_embedding = await _get_embedding(query)
        results = await _search_approved_copy(
            query_embedding=query_embedding,
            client_slug=client_slug,
            email_type=email_type,
            content_type=content_type,
            top_k=6,
        )

        if not results:
            filters = []
            if client_slug:
                filters.append(f"client='{client_slug}'")
            if email_type:
                filters.append(f"email_type='{email_type}'")
            if content_type:
                filters.append(f"content_type='{content_type}'")
            filter_str = f" with filters: {', '.join(filters)}" if filters else ""
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"No approved copy found matching '{query}'{filter_str}.",
                    }
                ]
            }

        formatted_results = []
        for i, result in enumerate(results, 1):
            similarity_pct = result["similarity"] * 100
            metadata = result.get("metadata", {})
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}

            client = metadata.get("client_slug") or metadata.get("company_name") or "Unknown"
            etype = metadata.get("email_type") or "N/A"
            ctype = metadata.get("content_type") or "N/A"

            formatted_results.append(
                f"### Example {i} (Relevance: {similarity_pct:.1f}%)\n"
                f"**Client:** {client} | **Email Type:** {etype} | **Content Type:** {ctype}\n\n"
                f"{result['content']}"
            )

        header = "## Approved Copy Examples"
        if client_slug:
            header += f": {client_slug}"

        response_text = (
            f"{header}\n\n"
            f"Found {len(results)} relevant examples:\n\n"
            + "\n\n---\n\n".join(formatted_results)
        )

        return {"content": [{"type": "text", "text": response_text}]}

    except Exception as e:
        return {
            "content": [
                {"type": "text", "text": f"Error searching approved copy: {str(e)}"}
            ],
            "is_error": True,
        }
