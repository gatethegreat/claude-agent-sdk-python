#!/usr/bin/env python3
"""
Interactive chat interface with MCP tools.

This example demonstrates a simple chat loop where you can interact with Claude
and Claude can use custom MCP tools to help answer your questions.
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
    # This is simulated - in real use, you'd call a weather API
    return {
        "content": [
            {
                "type": "text",
                "text": f"Weather in {location}: Sunny, 72°F (simulated data)",
            }
        ]
    }


@tool("calculate", "Perform a calculation", {"expression": str})
async def calculate(args: dict[str, Any]) -> dict[str, Any]:
    """Safely evaluate a mathematical expression."""
    expression = args["expression"]
    try:
        # Simple eval for demo - in production, use a safe math parser
        result = eval(expression, {"__builtins__": {}}, {})
        return {"content": [{"type": "text", "text": f"{expression} = {result}"}]}
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error calculating: {str(e)}"}],
            "is_error": True,
        }


@tool("search", "Search for information", {"query": str})
async def search(args: dict[str, Any]) -> dict[str, Any]:
    """Search for information (simulated)."""
    query = args["query"]
    # This is simulated - in real use, you'd call a search API
    return {
        "content": [
            {
                "type": "text",
                "text": f"Search results for '{query}': [Simulated results would appear here]",
            }
        ]
    }


def display_message(msg):
    """Display message content in a clean format."""
    if isinstance(msg, UserMessage):
        # Don't print user messages - we already showed them
        pass
    elif isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                print(f"\n🤖 Claude: {block.text}")
            elif isinstance(block, ToolUseBlock):
                print(f"   [Using tool: {block.name}]")
    elif isinstance(msg, SystemMessage):
        # Ignore system messages
        pass
    elif isinstance(msg, ResultMessage):
        # Show cost if available
        if msg.total_cost_usd:
            print(f"   💰 Cost: ${msg.total_cost_usd:.6f}")


async def chat_loop():
    """Run an interactive chat loop with MCP tools."""
    print("=" * 60)
    print("Interactive Chat with MCP Tools")
    print("=" * 60)
    print("\nAvailable tools:")
    print("  • get_weather - Get weather for a location")
    print("  • calculate - Perform calculations")
    print("  • search - Search for information")
    print("\nType 'quit' or 'exit' to end the chat")
    print("=" * 60)

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
        system_prompt="You are a helpful assistant with access to weather, calculation, and search tools. Use them when appropriate to help answer questions.",
    )

    # Start chat session
    async with ClaudeSDKClient(options=options) as client:
        while True:
            # Get user input
            try:
                user_input = input("\n👤 You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nGoodbye!")
                break

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "bye"]:
                print("\nGoodbye!")
                break

            # Send to Claude
            await client.query(user_input)

            # Display Claude's response
            async for msg in client.receive_response():
                display_message(msg)


async def main():
    """Main entry point."""
    try:
        await chat_loop()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
