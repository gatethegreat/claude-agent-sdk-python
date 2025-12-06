#!/usr/bin/env python3
"""
Demo of chat interface with MCP tools (non-interactive).

This demonstrates how the chat + MCP integration works with pre-defined queries.
"""

import asyncio
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
    tool,
)


# Define some example MCP tools
@tool("get_weather", "Get the weather for a location", {"location": str})
async def get_weather(args: dict[str, Any]) -> dict[str, Any]:
    """Get weather information for a location (simulated)."""
    location = args["location"]
    return {
        "content": [
            {
                "type": "text",
                "text": f"Weather in {location}: Sunny, 72°F, light breeze",
            }
        ]
    }


@tool("calculate", "Perform a calculation", {"expression": str})
async def calculate(args: dict[str, Any]) -> dict[str, Any]:
    """Safely evaluate a mathematical expression."""
    expression = args["expression"]
    try:
        # Simple eval for demo
        result = eval(expression, {"__builtins__": {}}, {})
        return {"content": [{"type": "text", "text": f"{expression} = {result}"}]}
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "is_error": True,
        }


@tool("search", "Search for information", {"query": str})
async def search(args: dict[str, Any]) -> dict[str, Any]:
    """Search for information (simulated)."""
    query = args["query"]
    return {
        "content": [
            {
                "type": "text",
                "text": f"Top results for '{query}':\n1. Python is a popular programming language\n2. It's used for web dev, AI, data science\n3. Created by Guido van Rossum",
            }
        ]
    }


def display_message(msg):
    """Display message content in a clean format."""
    if isinstance(msg, UserMessage):
        pass  # Don't print - we already showed it
    elif isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                print(f"🤖 Claude: {block.text}")
            elif isinstance(block, ToolUseBlock):
                print(f"   [Using tool: {block.name} with {block.input}]")
    elif isinstance(msg, SystemMessage):
        pass
    elif isinstance(msg, ResultMessage):
        if msg.total_cost_usd:
            print(f"   💰 Cost: ${msg.total_cost_usd:.6f}")


async def demo_chat():
    """Run a demo conversation with MCP tools."""
    print("=" * 70)
    print("DEMO: Interactive Chat with MCP Tools")
    print("=" * 70)
    print("\n📋 Available MCP Tools:")
    print("  • get_weather - Get weather for a location")
    print("  • calculate - Perform calculations")
    print("  • search - Search for information")
    print("\n" + "=" * 70)

    # Create MCP server with tools
    tools_server = create_sdk_mcp_server(
        name="chat-tools", version="1.0.0", tools=[get_weather, calculate, search]
    )

    # Configure options
    options = ClaudeAgentOptions(
        mcp_servers={"tools": tools_server},
        allowed_tools=[
            "mcp__tools__get_weather",
            "mcp__tools__calculate",
            "mcp__tools__search",
        ],
        system_prompt="You are a helpful assistant. When users ask about weather, use the get_weather tool. For math, use calculate. For info, use search.",
    )

    # Demo queries
    queries = [
        "What's the weather like in Paris?",
        "Calculate 25 * 4 + 10",
        "Tell me about Python programming",
    ]

    async with ClaudeSDKClient(options=options) as client:
        for i, query in enumerate(queries, 1):
            print(f"\n{'─' * 70}")
            print(f"Query {i}/{len(queries)}")
            print(f"{'─' * 70}")
            print(f"👤 You: {query}")

            await client.query(query)

            async for msg in client.receive_response():
                display_message(msg)

            print()  # Extra spacing

    print("=" * 70)
    print("Demo complete! This shows how Claude uses MCP tools to answer queries.")
    print("=" * 70)


async def main():
    """Main entry point."""
    try:
        await demo_chat()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
