# Test Agent - Calculator

A simple Claude agent with calculator MCP tools (add, multiply, divide).

## Structure

```
testAgent/
├── backend/
│   ├── main.py           # FastAPI server with WebSocket
│   ├── claude_client.py  # Claude SDK wrapper
│   ├── requirements.txt  # Python dependencies
│   └── tools/
│       ├── __init__.py   # Tool exports
│       └── calculator.py # Add, multiply, divide tools
├── frontend/
│   └── index.html        # Chat UI (single file, no build needed)
└── README.md
```

## Quick Start

### 1. Install dependencies

```bash
cd testAgent/backend
pip install -r requirements.txt
```

### 2. Run the backend server

```bash
cd testAgent/backend
python3 main.py
```

Server runs on http://localhost:8001

### 3. Open the frontend

Simply open the HTML file in your browser:

```bash
# Option 1: Direct file open (Windows)
start frontend/index.html

# Option 2: Use Python's HTTP server
cd testAgent/frontend
python3 -m http.server 3000
# Then open http://localhost:3000
```

### 4. CLI demo (alternative)

```bash
cd testAgent/backend
python3 claude_client.py
```

## API Endpoints

- `GET /` - Health check
- `GET /health` - Health check
- `WebSocket /ws` - Real-time chat

## WebSocket Protocol

### Connect
```json
{"type": "connect"}
```

### Send message
```json
{"type": "message", "content": "What is 5 + 3?"}
```

### Responses
```json
{"type": "stream_text", "content": "Let me calculate..."}
{"type": "tool_use_start", "tool_name": "add", "tool_id": "..."}
{"type": "assistant", "content": "...", "tools_used": ["add"]}
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `add` | Add two numbers | `a`, `b` (numbers) |
| `multiply` | Multiply two numbers | `a`, `b` (numbers) |
| `divide` | Divide a by b | `a`, `b` (numbers) |

## Example Usage

Ask the agent things like:
- "What is 5 + 3?"
- "Calculate 12 * 7"
- "Divide 100 by 4"
- "What is (5 + 3) * 2?" (chains operations)
