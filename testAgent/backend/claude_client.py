"""Claude SDK client wrapper for calculator agent."""

import asyncio
from typing import Any, AsyncIterator

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    ResultMessage,
    AssistantMessage,
    TextBlock,
)
from tools import ALL_TOOLS


class CalculatorClient:
    """Client wrapper for Claude SDK with calculator tools."""

    def __init__(self):
        self.client: ClaudeSDKClient | None = None
        self.sdk_session_id: str | None = None

    async def connect(self, resume_session_id: str | None = None) -> None:
        """Connect to the Claude SDK client."""
        # Build system prompt
        system_prompt = """You are a helpful calculator assistant. You have access to three math tools:
- add: Add two numbers together
- multiply: Multiply two numbers together
- divide: Divide one number by another

When the user asks you to perform calculations, use these tools to compute the results.
You can chain multiple operations together to solve complex expressions.

Always show your work by explaining what calculations you're performing."""

        # Configure MCP server with calculator tools using create_sdk_mcp_server
        calculator_server = create_sdk_mcp_server(
            name="calculator",
            tools=ALL_TOOLS,
        )

        mcp_servers = {
            "calculator": calculator_server,
        }

        # Build allowed tools list (only our calculator tools)
        allowed_tools = [
            "mcp__calculator__add",
            "mcp__calculator__multiply",
            "mcp__calculator__divide",
        ]

        # Configure options
        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            mcp_servers=mcp_servers,
            allowed_tools=allowed_tools,
            include_partial_messages=True,  # Enable real-time streaming with proper deltas
        )

        # Try to resume session if provided
        if resume_session_id:
            options.resume = resume_session_id

        # Create and connect client
        self.client = ClaudeSDKClient(options)
        await self.client.connect()

    async def disconnect(self) -> None:
        """Disconnect the Claude SDK client."""
        if self.client:
            await self.client.disconnect()
            self.client = None

    async def send_message(self, message: str) -> AsyncIterator[Any]:
        """Send a message and stream the response."""
        if not self.client:
            raise RuntimeError("Client not connected. Call connect() first.")

        # Send the query
        await self.client.query(message)

        # Stream the response
        async for msg in self.client.receive_response():
            # Capture session ID for resumption from ResultMessage
            if isinstance(msg, ResultMessage):
                if hasattr(msg, "session_id") and msg.session_id:
                    self.sdk_session_id = msg.session_id
            yield msg

    def get_session_id(self) -> str | None:
        """Get the current SDK session ID for resumption."""
        return self.sdk_session_id


async def main():
    """Simple CLI demo of the calculator client."""
    client = CalculatorClient()

    print("Starting calculator agent...")
    await client.connect()
    print("Calculator agent ready! Type 'quit' to exit.\n")

    try:
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                break
            if not user_input:
                continue

            print("Assistant: ", end="", flush=True)

            async for msg in client.send_message(user_input):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            print(block.text, end="", flush=True)
                elif isinstance(msg, ResultMessage):
                    print()  # newline after response

            print()

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        await client.disconnect()
        print("Calculator agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())
