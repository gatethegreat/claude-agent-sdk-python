# MCP Tools Development Guide

Complete guide for creating custom MCP tools for the Claude Agent SDK.

## Table of Contents

1. [Quick Start](#quick-start)
2. [The @tool Decorator](#the-tool-decorator)
3. [Input Schema Formats](#input-schema-formats)
4. [Response Formats](#response-formats)
5. [Error Handling](#error-handling)
6. [Creating an MCP Server](#creating-an-mcp-server)
7. [Integration with ClaudeSDKClient](#integration-with-claudesdkclient)
8. [Tool Permissions & Restrictions](#tool-permissions--restrictions)
9. [Permission Callbacks](#permission-callbacks)
10. [Code Examples](#code-examples)
11. [Best Practices](#best-practices)
12. [Reference](#reference)

---

## Quick Start

```python
from typing import Any
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeSDKClient, ClaudeAgentOptions

# 1. Define a tool
@tool("greet", "Greet a user by name", {"name": str})
async def greet(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"Hello, {args['name']}!"}]}

# 2. Create MCP server
server = create_sdk_mcp_server(name="my-tools", tools=[greet])

# 3. Configure and use
options = ClaudeAgentOptions(
    mcp_servers={"tools": server},
    allowed_tools=["mcp__tools__greet"]
)

async with ClaudeSDKClient(options=options) as client:
    await client.query("Greet Alice")
    async for message in client.receive_response():
        print(message)
```

---

## The @tool Decorator

The `@tool` decorator creates an `SdkMcpTool` instance from an async function.

### Signature

```python
@tool(name: str, description: str, input_schema: dict | type)
async def tool_function(args: dict[str, Any]) -> dict[str, Any]:
    ...
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Unique tool identifier (used in `mcp__server__name`) |
| `description` | `str` | Human-readable description for Claude |
| `input_schema` | `dict` or `type` | Parameter definitions |

### The SdkMcpTool Object

After decoration, your function becomes an `SdkMcpTool` with these attributes:

```python
@tool("example", "An example tool", {"param": str})
async def example_tool(args):
    ...

# Access attributes
example_tool.name          # "example"
example_tool.description   # "An example tool"
example_tool.input_schema  # {"param": str}
example_tool.handler       # The original async function
```

---

## Input Schema Formats

### Simple Dictionary (Recommended)

Maps parameter names to Python types:

```python
@tool("add", "Add two numbers", {"a": float, "b": float})
async def add(args: dict[str, Any]) -> dict[str, Any]:
    result = args["a"] + args["b"]
    return {"content": [{"type": "text", "text": str(result)}]}
```

**Type Mapping:**
| Python Type | JSON Schema Type |
|-------------|------------------|
| `str` | `"string"` |
| `int` | `"integer"` |
| `float` | `"number"` |
| `bool` | `"boolean"` |

### No Parameters

Use empty dict for tools that don't need input:

```python
@tool("get_time", "Get current time", {})
async def get_time(args: dict[str, Any]) -> dict[str, Any]:
    from datetime import datetime
    return {"content": [{"type": "text", "text": datetime.now().isoformat()}]}
```

### TypedDict (For Type Hints)

```python
from typing import TypedDict

class SearchInput(TypedDict):
    query: str
    max_results: int

@tool("search", "Search for items", SearchInput)
async def search(args: SearchInput) -> dict[str, Any]:
    query = args["query"]
    limit = args["max_results"]
    ...
```

### Full JSON Schema (Advanced)

For optional parameters or complex validation:

```python
@tool("search", "Search with options", {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query"},
        "limit": {"type": "integer", "default": 10}
    },
    "required": ["query"]  # limit is optional
})
async def search(args: dict[str, Any]) -> dict[str, Any]:
    query = args["query"]
    limit = args.get("limit", 10)
    ...
```

---

## Response Formats

Tools must return a dict with a `content` key containing a list of content blocks.

### Text Response

```python
return {
    "content": [
        {"type": "text", "text": "Your response here"}
    ]
}
```

### Multiple Text Blocks

```python
return {
    "content": [
        {"type": "text", "text": "First paragraph..."},
        {"type": "text", "text": "Second paragraph..."}
    ]
}
```

### Image Response

```python
import base64

with open("chart.png", "rb") as f:
    image_data = base64.b64encode(f.read()).decode("utf-8")

return {
    "content": [
        {"type": "text", "text": "Here's your chart:"},
        {"type": "image", "data": image_data, "mimeType": "image/png"}
    ]
}
```

**Supported MIME Types:** `image/png`, `image/jpeg`, `image/gif`, `image/webp`

---

## Error Handling

### Returning Errors

Use `is_error: True` to indicate tool failure:

```python
@tool("divide", "Divide two numbers", {"a": float, "b": float})
async def divide(args: dict[str, Any]) -> dict[str, Any]:
    if args["b"] == 0:
        return {
            "content": [{"type": "text", "text": "Error: Division by zero"}],
            "is_error": True
        }
    return {"content": [{"type": "text", "text": str(args["a"] / args["b"])}]}
```

### Exception Handling

```python
@tool("fetch_data", "Fetch data from API", {"url": str})
async def fetch_data(args: dict[str, Any]) -> dict[str, Any]:
    try:
        result = await some_api_call(args["url"])
        return {"content": [{"type": "text", "text": result}]}
    except ConnectionError as e:
        return {
            "content": [{"type": "text", "text": f"Connection failed: {e}"}],
            "is_error": True
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Unexpected error: {e}"}],
            "is_error": True
        }
```

### Helper Functions

```python
def tool_response(text: str) -> dict[str, Any]:
    """Standard success response."""
    return {"content": [{"type": "text", "text": text}]}

def tool_error(message: str) -> dict[str, Any]:
    """Standard error response."""
    return {
        "content": [{"type": "text", "text": f"Error: {message}"}],
        "is_error": True
    }
```

---

## Creating an MCP Server

### Basic Server

```python
from claude_agent_sdk import create_sdk_mcp_server

server = create_sdk_mcp_server(
    name="my-tools",
    version="1.0.0",  # Optional, defaults to "1.0.0"
    tools=[tool1, tool2, tool3]
)
```

### Multiple Servers

```python
math_server = create_sdk_mcp_server(name="math", tools=[add, subtract, multiply])
data_server = create_sdk_mcp_server(name="data", tools=[fetch_data, search])

options = ClaudeAgentOptions(
    mcp_servers={
        "math": math_server,
        "data": data_server
    },
    allowed_tools=[
        "mcp__math__add",
        "mcp__math__multiply",
        "mcp__data__search"
    ]
)
```

---

## Integration with ClaudeSDKClient

### Tool Naming Convention

Tools are referenced as: `mcp__<server_key>__<tool_name>`

- `server_key`: The key in `mcp_servers` dict
- `tool_name`: The name passed to `@tool`

```python
server = create_sdk_mcp_server(name="calculator", tools=[add_tool])

options = ClaudeAgentOptions(
    mcp_servers={"calc": server},  # server_key is "calc"
    allowed_tools=["mcp__calc__add"]  # mcp__calc__add
)
```

### Dynamic Tool Registration

```python
ALL_TOOLS = [tool1, tool2, tool3]

server = create_sdk_mcp_server(name="tools", tools=ALL_TOOLS)

options = ClaudeAgentOptions(
    mcp_servers={"tools": server},
    allowed_tools=[f"mcp__tools__{t.name}" for t in ALL_TOOLS]
)
```

---

## Tool Permissions & Restrictions

The SDK provides two key parameters to control which tools Claude can use:

### allowed_tools

Whitelist of tools Claude can use. Only these tools will be available:

```python
options = ClaudeAgentOptions(
    mcp_servers={"tools": server},
    allowed_tools=[
        # Your custom MCP tools
        "mcp__tools__get_client_names",
        "mcp__tools__queue_campaign",
        # Built-in tools you want to allow
        "WebSearch",
        "WebFetch",
        "Task",
        "TodoWrite",
    ]
)
```

### disallowed_tools

Explicitly block specific built-in tools. This is useful to ensure certain tools are never available:

```python
options = ClaudeAgentOptions(
    mcp_servers={"tools": server},
    allowed_tools=[...],
    disallowed_tools=[
        # File operations
        "Read", "Write", "Edit", "MultiEdit",
        # Code search
        "Glob", "Grep",
        # Terminal
        "Bash", "BashOutput", "KillShell",
        # Planning
        "EnterPlanMode", "ExitPlanMode",
        # Other
        "NotebookEdit", "Skill", "SlashCommand", "AskUserQuestion",
    ]
)
```

### Built-in Tools Reference

| Tool | Category | Description |
|------|----------|-------------|
| `Read` | File | Read files from filesystem |
| `Write` | File | Create or overwrite files |
| `Edit` | File | Make string replacements in files |
| `MultiEdit` | File | Multiple edits in one operation |
| `Glob` | Search | Find files using patterns |
| `Grep` | Search | Search file contents with regex |
| `Bash` | Terminal | Execute shell commands |
| `BashOutput` | Terminal | Get output from background shell |
| `KillShell` | Terminal | Kill background shell |
| `WebSearch` | Web | Search the web |
| `WebFetch` | Web | Fetch content from URLs |
| `Task` | Task | Launch specialized agents |
| `TodoWrite` | Task | Manage task lists |
| `EnterPlanMode` | Planning | Enter planning mode |
| `ExitPlanMode` | Planning | Exit planning mode |
| `NotebookEdit` | Jupyter | Edit notebook cells |
| `Skill` | Other | Execute skills |
| `SlashCommand` | Other | Execute slash commands |
| `AskUserQuestion` | Other | Ask user questions |

### Permission Modes

Control overall tool permission behavior:

```python
options = ClaudeAgentOptions(
    permission_mode="default"  # or "acceptEdits", "bypassPermissions", "plan"
)
```

| Mode | Description |
|------|-------------|
| `default` | Normal permission checks |
| `acceptEdits` | Auto-accept file edits |
| `bypassPermissions` | All tools auto-approved (use with caution) |
| `plan` | Read-only tools only |

### Example: Marketing-Only Agent

Restrict Claude to only marketing tools, no file/code access:

```python
from tools import ALL_TOOLS

# Build allowed tools list
allowed_tools = [f"mcp__chat-tools__{t.name}" for t in ALL_TOOLS]
allowed_tools.extend(["WebSearch", "WebFetch", "Task", "TodoWrite"])

# Explicitly disable development tools
disallowed_tools = [
    "Read", "Write", "Edit", "MultiEdit",
    "Glob", "Grep",
    "Bash", "BashOutput", "KillShell",
    "EnterPlanMode", "ExitPlanMode",
    "NotebookEdit", "Skill", "SlashCommand", "AskUserQuestion",
]

options = ClaudeAgentOptions(
    mcp_servers={"chat-tools": tools_server},
    allowed_tools=allowed_tools,
    disallowed_tools=disallowed_tools,
    system_prompt="You are a marketing strategist...",
)
```

---

## Permission Callbacks

Fine-grained control over tool execution.

### Basic Permission Callback

```python
from claude_agent_sdk.types import (
    ToolPermissionContext,
    PermissionResultAllow,
    PermissionResultDeny
)

async def permission_callback(
    tool_name: str,
    input_data: dict[str, Any],
    context: ToolPermissionContext
) -> PermissionResultAllow | PermissionResultDeny:

    if tool_name in ["mcp__tools__search", "mcp__tools__get_info"]:
        return PermissionResultAllow()

    if "delete" in tool_name.lower():
        return PermissionResultDeny(message="Delete operations not allowed")

    return PermissionResultDeny(message="Tool not permitted")

options = ClaudeAgentOptions(
    mcp_servers={"tools": server},
    can_use_tool=permission_callback,
    permission_mode="default"
)
```

### Modifying Tool Input

```python
async def permission_callback(
    tool_name: str,
    input_data: dict[str, Any],
    context: ToolPermissionContext
) -> PermissionResultAllow | PermissionResultDeny:

    if tool_name == "mcp__tools__search":
        modified_input = input_data.copy()
        if "limit" not in modified_input:
            modified_input["limit"] = 10
        return PermissionResultAllow(updated_input=modified_input)

    return PermissionResultAllow()
```

---

## Code Examples

### Basic Tools

```python
@tool("add", "Add two numbers", {"a": float, "b": float})
async def add(args: dict[str, Any]) -> dict[str, Any]:
    result = args["a"] + args["b"]
    return {"content": [{"type": "text", "text": f"{args['a']} + {args['b']} = {result}"}]}

@tool("get_current_time", "Get the current date and time", {})
async def get_current_time(args: dict[str, Any]) -> dict[str, Any]:
    from datetime import datetime
    now = datetime.now()
    return {"content": [{"type": "text", "text": f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}"}]}
```

### Database Tool (PostgreSQL)

```python
import asyncpg

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"), min_size=1, max_size=5)
    return _pool

@tool("query_users", "Search for users by email domain", {"domain": str})
async def query_users(args: dict[str, Any]) -> dict[str, Any]:
    domain = args.get("domain", "").strip()
    if not domain:
        return {"content": [{"type": "text", "text": "Error: domain is required"}], "is_error": True}

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, email FROM users WHERE email LIKE $1 LIMIT 10",
                f"%@{domain}"
            )
        if not rows:
            return {"content": [{"type": "text", "text": f"No users found with @{domain}"}]}
        result = "\n".join(f"• {r['name']} ({r['email']})" for r in rows)
        return {"content": [{"type": "text", "text": f"Users with @{domain}:\n{result}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Database error: {e}"}], "is_error": True}
```

### Google Sheets Tool

```python
import gspread
from oauth2client.service_account import ServiceAccountCredentials

_gspread_client = None

def get_sheets_client():
    global _gspread_client
    if _gspread_client is None:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"), scope
        )
        _gspread_client = gspread.authorize(creds)
    return _gspread_client

@tool("read_sheet", "Read data from a Google Sheet", {"sheet_id": str, "sheet_name": str})
async def read_sheet(args: dict[str, Any]) -> dict[str, Any]:
    try:
        client = get_sheets_client()
        spreadsheet = client.open_by_key(args["sheet_id"])
        worksheet = spreadsheet.worksheet(args.get("sheet_name", "Sheet1"))
        records = worksheet.get_all_records()

        if not records:
            return {"content": [{"type": "text", "text": "No data found"}]}

        headers = list(records[0].keys())
        lines = [" | ".join(headers), "-" * 50]
        for record in records[:20]:
            lines.append(" | ".join(str(record.get(h, "")) for h in headers))

        return {"content": [{"type": "text", "text": "\n".join(lines)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "is_error": True}
```

### Vector Search (PGVector + OpenAI)

```python
from openai import OpenAI

openai_client = None

def get_openai():
    global openai_client
    if openai_client is None:
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return openai_client

@tool("semantic_search", "Search documents by semantic similarity", {"query": str, "limit": int})
async def semantic_search(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query", "").strip()
    limit = args.get("limit", 5)

    if not query:
        return {"content": [{"type": "text", "text": "Error: query is required"}], "is_error": True}

    try:
        # Generate embedding
        client = get_openai()
        response = client.embeddings.create(model="text-embedding-3-small", input=query)
        embedding = response.data[0].embedding

        # Search database
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT content, 1 - (embedding <=> $1::vector) as similarity
                FROM documents
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """, str(embedding), limit)

        results = []
        for i, row in enumerate(rows, 1):
            sim = row['similarity'] * 100
            results.append(f"### Result {i} ({sim:.1f}% match)\n{row['content'][:500]}...")

        return {"content": [{"type": "text", "text": "\n\n".join(results)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Search error: {e}"}], "is_error": True}
```

### Retry Logic

```python
import asyncio

async def retry_async(func, max_retries=3, delay=1):
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(delay * (2 ** attempt))

@tool("reliable_fetch", "Fetch with retries", {"url": str})
async def reliable_fetch(args: dict[str, Any]) -> dict[str, Any]:
    async def fetch():
        async with aiohttp.ClientSession() as session:
            async with session.get(args["url"], timeout=10) as response:
                response.raise_for_status()
                return await response.text()

    try:
        content = await retry_async(fetch, max_retries=3)
        return {"content": [{"type": "text", "text": content[:2000]}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Failed after 3 retries: {e}"}], "is_error": True}
```

---

## Best Practices

### 1. Tool Organization

```
tools/
├── __init__.py      # Exports ALL_TOOLS
├── config.py        # Environment configuration
├── search.py        # Search-related tools
├── data.py          # Data processing tools
└── external.py      # External API tools
```

### 2. Descriptive Names and Descriptions

```python
# Good
@tool(
    "search_knowledge_base",
    "Search the company knowledge base for relevant documents. Returns up to 6 most relevant results.",
    {"query": str, "client_name": str}
)

# Bad
@tool("search", "Search stuff", {"q": str})
```

### 3. Input Validation

```python
@tool("process", "Process data", {"data": str, "format": str})
async def process(args: dict[str, Any]) -> dict[str, Any]:
    data = args.get("data", "").strip()
    format_type = args.get("format", "").lower()

    if not data:
        return tool_error("data is required")

    if format_type not in ["json", "csv", "xml"]:
        return tool_error(f"Invalid format '{format_type}'")

    # Process...
```

### 4. Lazy Loading Dependencies

```python
openai_client = None

def _get_openai_client():
    global openai_client
    if openai_client is None:
        from openai import OpenAI
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return openai_client
```

### 5. Testing Tools

```python
import asyncio

async def test_my_tool():
    result = await my_tool.handler({"param": "test"})
    assert "content" in result
    assert result["content"][0]["type"] == "text"
    print("Test passed!")

asyncio.run(test_my_tool())
```

---

## Reference

### Key Imports

```python
from claude_agent_sdk import (
    # Tool creation
    tool,
    create_sdk_mcp_server,
    SdkMcpTool,
    # Client
    ClaudeSDKClient,
    ClaudeAgentOptions,
    # Message types
    AssistantMessage,
    UserMessage,
    SystemMessage,
    ResultMessage,
    # Content blocks
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)

from claude_agent_sdk.types import (
    # Permission types
    ToolPermissionContext,
    PermissionResultAllow,
    PermissionResultDeny,
)
```

### ClaudeAgentOptions Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `allowed_tools` | `list[str]` | Whitelist of allowed tools |
| `disallowed_tools` | `list[str]` | Blacklist of blocked tools |
| `system_prompt` | `str` | System prompt for Claude |
| `mcp_servers` | `dict` | MCP server configurations |
| `permission_mode` | `str` | Permission behavior mode |
| `can_use_tool` | `callable` | Permission callback function |
| `include_partial_messages` | `bool` | Enable streaming partial messages |
| `max_turns` | `int` | Maximum conversation turns |
| `max_budget_usd` | `float` | Maximum cost budget |
| `resume` | `str` | Session ID to resume |
