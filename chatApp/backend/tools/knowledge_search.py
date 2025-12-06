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
        model="text-embedding-3-small",  # Must match the model used to create DB embeddings
        input=text,
    )

    return response.data[0].embedding


async def _search_vectors(
    query_embedding: list[float],
    client_name: str,
    top_k: int = 6,
) -> list[dict]:
    """
    Search pgvector store for similar documents.

    Args:
        query_embedding: The query embedding vector
        client_name: Filter by company_name in metadata
        top_k: Number of results to return
    """
    from .config import config

    pool = await _get_db_pool()

    # Build the query - searches for similar embeddings filtered by metadata
    # The metadata column contains JSON with company_name field
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
        # Convert embedding list to PostgreSQL vector format
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

    await pool.close()


@tool(
    "company_background_search",
    (
        "Search for relevant company background information from the knowledge base. "
        "IMPORTANT: You MUST verify the client_name parameter is spelled correctly "
        "before using this tool. If unsure about the exact spelling, first call "
        "get_client_names to get the list of valid client names. "
        "Returns up to 6 most relevant documents matching the query."
    ),
    {
        "client_name": str,  # The exact company name to filter by
        "query": str,  # The search query to find relevant information
    },
)
async def company_background_search(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search company background knowledge base using semantic similarity.

    This tool:
    1. Generates an embedding for the query using OpenAI
    2. Searches the pgvector store filtered by company_name metadata
    3. Returns the top_k most similar documents

    Args:
        args: Dictionary containing:
            - client_name: The exact company name (must match metadata)
            - query: The search query
    """
    client_name = args.get("client_name", "").strip()
    query = args.get("query", "").strip()

    # Validate inputs
    if not client_name:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Error: client_name is required. "
                        "Please use get_client_names first to verify the correct spelling."
                    ),
                }
            ],
            "is_error": True,
        }

    if not query:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: query is required. What would you like to search for?",
                }
            ],
            "is_error": True,
        }

    try:
        from .config import config

        if not config.validate_pgvector():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Error: Database credentials not configured. "
                            "Set SUPABASE_DB_URL and OPENAI_API_KEY environment variables."
                        ),
                    }
                ],
                "is_error": True,
            }

        # Generate embedding for the query
        query_embedding = await _get_embedding(query)

        # Search the vector store
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
                        "text": (
                            f"No results found for client '{client_name}' matching query '{query}'. "
                            "This could mean:\n"
                            "1. The client name is misspelled (use get_client_names to verify)\n"
                            "2. No documents exist for this client\n"
                            "3. The query doesn't match any stored information"
                        ),
                    }
                ]
            }

        # Format results
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
                {
                    "type": "text",
                    "text": f"Error searching knowledge base: {str(e)}",
                }
            ],
            "is_error": True,
        }
