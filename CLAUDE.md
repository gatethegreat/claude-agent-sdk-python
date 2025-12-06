# Important

- use subase mcp to see the database that you are working with

# Workflow

```bash
# Lint and style
# Check for issues and fix automatically
python -m ruff check src/ tests/ --fix
python -m ruff format src/ tests/

# Typecheck (only done for src/)
python -m mypy src/

# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_client.py
```

# Codebase Structure

- `src/claude_agent_sdk/` - Main package
  - `client.py` - ClaudeSDKClient for interactive sessions
  - `query.py` - One-shot query function
  - `types.py` - Type definitions
  - `_internal/` - Internal implementation details
    - `transport/subprocess_cli.py` - CLI subprocess management
    - `message_parser.py` - Message parsing logic

- `chatApp/` - Full-stack chat application demo
  - `backend/` - FastAPI server with WebSocket streaming
    - `main.py` - API endpoints and WebSocket handler
    - `claude_client.py` - SDK wrapper (uses `include_partial_messages=True` for real-time streaming)
    - `database.py` - SQLite session and message storage
    - `tools/` - Custom MCP tools folder
    - **`TOOLS.md`** - **READ THIS for creating MCP tools**
    - `TOOL_EXAMPLES.md` - Code examples for common tool patterns
  - `frontend/` - React + Vite chat UI
    - Session management (create/resume/delete)
    - Message history persistence
    - Real-time streaming display

# Chat App

```bash
# Start backend (http://localhost:8000)
cd chatApp/backend && python3 main.py

# Start frontend (http://localhost:5173 or next available port)
cd chatApp/frontend && npm run dev

# Kill all servers
pkill -9 -f "python3 main.py" && pkill -9 -f "npm run dev"
lsof -ti:8000,5173,3001 | xargs kill -9 2>/dev/null
```

**Key**: Always use `include_partial_messages=True` in ClaudeAgentOptions for real-time streaming.
