# Chat App Tools

Custom MCP tools for the chat application.

## Structure

```
tools/
├── __init__.py          # Exports ALL_TOOLS list
├── config.py            # Environment configuration
├── client_lookup.py     # Google Sheets client lookup
├── knowledge_search.py  # PGVector semantic search
└── README.md            # This file
```

## Available Tools

### `get_client_names`

Fetches all active client names from Google Sheets.

- **Parameters:** None
- **Returns:** List of active client names
- **Use Case:** Verify client name spelling before using other client-specific tools

```python
@tool(
    "get_client_names",
    "Read all active client names from the master client list...",
    {}
)
```

### `company_background_search`

Searches the PGVector knowledge base for company information.

- **Parameters:**
  - `client_name` (str): Exact company name (must match metadata)
  - `query` (str): Search query for relevant information
- **Returns:** Up to 6 most relevant documents with similarity scores
- **Use Case:** Retrieve company background, brand info, products, etc.

```python
@tool(
    "company_background_search",
    "Search for relevant company background information...",
    {"client_name": str, "query": str}
)
```

## Configuration

Tools are configured via environment variables. Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

### Required Variables

| Variable | Description |
|----------|-------------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path to Google service account JSON file |
| `GOOGLE_SPREADSHEET_ID` | Google Sheets document ID |
| `GOOGLE_SHEET_NAME` | Sheet name containing client data |
| `SUPABASE_DB_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | OpenAI API key for embeddings |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PGVECTOR_TABLE_NAME` | `documents` | Table name for vector search |
| `PGVECTOR_CONTENT_COLUMN` | `content` | Content column name |
| `PGVECTOR_EMBEDDING_COLUMN` | `embedding` | Embedding column name |
| `PGVECTOR_METADATA_COLUMN` | `metadata` | Metadata column name |

## Adding New Tools

### 1. Create Tool File

```python
# tools/my_new_tool.py
from typing import Any
from claude_agent_sdk import tool

@tool("my_tool", "Description of what the tool does", {"param": str})
async def my_tool(args: dict[str, Any]) -> dict[str, Any]:
    param = args.get("param", "")

    # Your logic here
    result = process(param)

    return {
        "content": [{"type": "text", "text": result}]
    }
```

### 2. Export in `__init__.py`

```python
# tools/__init__.py
from .client_lookup import get_client_names
from .knowledge_search import company_background_search
from .my_new_tool import my_tool  # Add import

ALL_TOOLS = [
    get_client_names,
    company_background_search,
    my_tool,  # Add to list
]
```

### 3. Test the Tool

```python
import asyncio
from tools.my_new_tool import my_tool

async def test():
    result = await my_tool.handler({"param": "test"})
    print(result)

asyncio.run(test())
```

## Tool Response Format

All tools must return this structure:

```python
{
    "content": [
        {"type": "text", "text": "Response text here"}
    ]
}
```

For errors:

```python
{
    "content": [{"type": "text", "text": "Error message"}],
    "is_error": True
}
```

## Dependencies

Install required packages:

```bash
pip install gspread oauth2client asyncpg openai python-dotenv
```

Or use requirements.txt:

```bash
pip install -r requirements.txt
```

## Important Notes

### Embedding Model

The knowledge search uses `text-embedding-3-small`. This **must match** the model used to create embeddings in your database. If you change models, you'll need to re-embed all documents.

### Google Sheets Access

The service account email must have access to the Google Sheet:
1. Open your Google Sheet
2. Click "Share"
3. Add the service account email (from your JSON file)
4. Grant "Viewer" access

### Database Schema

Expected `documents` table structure:

```sql
CREATE TABLE documents (
    id bigint PRIMARY KEY,
    content text,
    metadata jsonb,  -- Must contain company_name field
    embedding vector(1536),
    created_at timestamp,
    updated_at timestamp
);
```

The `metadata` column must have a `company_name` field for filtering:

```json
{"company_name": "Client Name", ...}
```
