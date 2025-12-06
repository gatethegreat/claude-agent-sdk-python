# Copywriting Agent

A Claude agent for creating marketing copy with access to company knowledge and approved copy examples.

## Tools

| Tool | Description |
|------|-------------|
| `company_background_search` | Search company knowledge base for brand voice, products, values |
| `approved_copy_search` | Search approved copy examples for style/tone reference |

## Quick Start

### 1. Set up environment variables

```bash
cd copyAgent/backend
cp .env.example .env
# Edit .env with your credentials
```

Required:
- `SUPABASE_DB_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - For generating embeddings

### 2. Install dependencies

```bash
cd copyAgent/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the backend server

```bash
cd copyAgent/backend
source venv/bin/activate
python3 main.py
```

Server runs on http://localhost:8002

### 4. Open the frontend

```bash
# Option 1: Direct file open
start frontend/index.html  # Windows
open frontend/index.html   # Mac

# Option 2: Python HTTP server
cd copyAgent/frontend
python3 -m http.server 3000
# Then open http://localhost:3000
```

## Usage

1. Enter the client name in the header input
2. Ask the agent to write copy:
   - "Write 5 email subject lines for a holiday sale"
   - "Create a product description for our bestseller"
   - "Write social media ad copy for a new product launch"

The agent will:
1. Search company background for brand context
2. Search approved copy for style reference
3. Generate copy matching the brand voice

## Database Tables

### `documents` (Company Background)
- `content` - Text content
- `embedding` - Vector embedding
- `metadata` - JSON with `company_name` field

### `approved_copy` (Approved Copy Examples)
- `content` - The approved copy text
- `embedding` - Vector embedding
- `metadata` - JSON with `company_name` and `type` fields
