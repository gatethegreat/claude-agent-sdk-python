"""
PGVector knowledge search tool.

Performs semantic search on a PostgreSQL database with pgvector extension
to retrieve relevant company background information.
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


async def _search_vectors(
    query_embedding: list[float],
    client_name: str,
    top_k: int = 6,
) -> list[dict]:
    """Search pgvector store for similar documents."""
    from .config import config

    pool = await _get_db_pool()

    query = f"""
        SELECT
            {config.PGVECTOR_CONTENT_COLUMN},
            {config.PGVECTOR_METADATA_COLUMN},
            1 - ({config.PGVECTOR_EMBEDDING_COLUMN} <=> $1::vector) as similarity
        FROM {config.PGVECTOR_TABLE_NAME}
        WHERE {config.PGVECTOR_METADATA_COLUMN}->>'company_name' = $2
        ORDER BY {config.PGVECTOR_EMBEDDING_COLUMN} <=> $1::vector
        LIMIT $3
    """

    async with pool.acquire() as conn:
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        rows = await conn.fetch(query, embedding_str, client_name, top_k)

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
    "company_background_search",
    (
        "Search for relevant company background information from the knowledge base. "
        "Use this to understand the brand voice, products, and company information "
        "before writing copy. Returns up to 6 most relevant documents."
    ),
    {
        "client_name": str,  # The exact company name to filter by
        "query": str,  # The search query to find relevant information
    },
)
async def company_background_search(args: dict[str, Any]) -> dict[str, Any]:
    """Search company background knowledge base using semantic similarity."""
    client_name = args.get("client_name", "").strip()
    query = args.get("query", "").strip()

    if not client_name:
        return {
            "content": [{"type": "text", "text": "Error: client_name is required."}],
            "is_error": True,
        }

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
        results = await _search_vectors(
            query_embedding=query_embedding,
            client_name=client_name,
            top_k=6,
        )

        if not results:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"No results found for client '{client_name}' matching query '{query}'.",
                    }
                ]
            }

        formatted_results = []
        for i, result in enumerate(results, 1):
            similarity_pct = result["similarity"] * 100
            formatted_results.append(
                f"### Result {i} (Relevance: {similarity_pct:.1f}%)\n\n{result['content']}"
            )

        response_text = (
            f"## Company Background: {client_name}\n\n"
            f"Found {len(results)} relevant documents:\n\n"
            + "\n\n---\n\n".join(formatted_results)
        )

        return {"content": [{"type": "text", "text": response_text}]}

    except Exception as e:
        return {
            "content": [
                {"type": "text", "text": f"Error searching knowledge base: {str(e)}"}
            ],
            "is_error": True,
        }
