"""Claude SDK client wrapper for copywriting agent."""

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


class CopywritingClient:
    """Client wrapper for Claude SDK with copywriting tools."""

    def __init__(self):
        self.client: ClaudeSDKClient | None = None
        self.sdk_session_id: str | None = None
        self.client_name: str | None = None

    def set_client_name(self, client_name: str):
        """Set the client name for this session."""
        self.client_name = client_name

    async def connect(self, resume_session_id: str | None = None) -> None:
        """Connect to the Claude SDK client."""
        # Build system prompt for copywriting
        client_context = f" for {self.client_name}" if self.client_name else ""

        system_prompt = f"""You are an expert copywriter assistant{client_context}. You help create compelling marketing copy including:
- Email subject lines and body copy
- Product descriptions
- Ad copy (social media, display, search)
- Landing page copy
- Headlines and taglines

You have access to three important tools:

1. **get_client_names**: ALWAYS call this FIRST to get the list of active clients and their
   Client IDs. This ensures you use the correct client_slug/client_name for searches.

2. **company_background_search**: Use this to research the company's brand voice, products,
   values, and background information. Pass the Client ID from get_client_names as client_name.

3. **approved_copy_search**: Use this to find examples of previously approved copy.
   Reference these examples to match the established style and tone.
   Pass the Client ID as client_slug. Optional filters: email_type, content_type.

Workflow:
1. FIRST call get_client_names to get the correct Client ID
2. Search company_background_search for brand context (using Client ID as client_name)
3. Search approved_copy_search for style/tone reference examples (using Client ID as client_slug)
4. Write copy that matches the brand voice and approved style
5. Explain your creative choices when presenting the copy

Always be creative but stay true to the brand voice found in your research."""

        # Configure MCP server with copywriting tools
        copy_server = create_sdk_mcp_server(
            name="copywriting",
            tools=ALL_TOOLS,
        )

        mcp_servers = {
            "copywriting": copy_server,
        }

        # Build allowed tools list
        allowed_tools = [
            "mcp__copywriting__get_client_names",
            "mcp__copywriting__company_background_search",
            "mcp__copywriting__approved_copy_search",
        ]

        # Configure options
        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            mcp_servers=mcp_servers,
            allowed_tools=allowed_tools,
            include_partial_messages=True,  # Enable real-time streaming
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
    """Simple CLI demo of the copywriting client."""
    client = CopywritingClient()

    print("Starting copywriting agent...")
    client_name = input("Enter client name (or press Enter to skip): ").strip()
    if client_name:
        client.set_client_name(client_name)

    await client.connect()
    print("Copywriting agent ready! Type 'quit' to exit.\n")

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
        print("Copywriting agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())
