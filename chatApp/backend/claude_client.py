"""
Claude SDK client wrapper for the chat application.

Manages the Claude SDK client lifecycle and message streaming.
"""

import asyncio
from typing import AsyncIterator, Optional
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    AssistantMessage,
    UserMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)
from claude_agent_sdk.types import StreamEvent
from tools import ALL_TOOLS


class ChatClient:
    """Wrapper around ClaudeSDKClient for chat application."""

    def __init__(self):
        self.client: Optional[ClaudeSDKClient] = None
        self.current_session_id: Optional[str] = None
        self.resume_session_id: Optional[str] = None
        self.client_context: Optional[dict] = None

    def set_client_context(self, context: dict):
        """Set the client context for this chat session."""
        self.client_context = context

    def _create_options(self) -> ClaudeAgentOptions:
        """Create base Claude SDK options with MCP tools."""
        # Create MCP server with all tools
        tools_server = create_sdk_mcp_server(
            name="chat-tools", version="1.0.0", tools=ALL_TOOLS
        )

        # Build allowed tools list - ONLY our MCP tools plus WebSearch/WebFetch
        # Note: tool objects have a 'name' attribute from the @tool decorator
        allowed_tools = [f"mcp__chat-tools__{t.name}" for t in ALL_TOOLS]

        # Add web research tools (useful for marketing research)
        allowed_tools.extend(["WebSearch", "WebFetch"])

        # Add task management tools (useful for complex campaign planning)
        allowed_tools.extend(["Task", "TodoWrite"])

        # Explicitly disable all built-in development tools
        disallowed_tools = [
            "Read", "Write", "Edit", "MultiEdit",  # File operations
            "Glob", "Grep",  # Code search
            "Bash", "BashOutput", "KillShell",  # Terminal
            "EnterPlanMode", "ExitPlanMode",  # Planning
            "NotebookEdit",  # Jupyter
            "Skill", "SlashCommand",  # Other
            "AskUserQuestion",  # Interaction
        ]

        # Build system prompt with client context
        client_name = "Unknown Client"
        discount_guidelines = None
        copywriting_guidelines = None
        if self.client_context:
            client_name = self.client_context.get("clientName", "Unknown Client")
            discount_guidelines = self.client_context.get("discountGuidelines")
            copywriting_guidelines = self.client_context.get("copywritingGuidelines")

        # Build guidelines section if available
        guidelines_section = ""
        if discount_guidelines or copywriting_guidelines:
            guidelines_section = "\n\n=== CLIENT GUIDELINES (MUST FOLLOW) ===\n"
            if discount_guidelines:
                guidelines_section += f"\nDISCOUNT/OFFER GUIDELINES:\n{discount_guidelines}\n"
            if copywriting_guidelines:
                guidelines_section += f"\nCOPYWRITING GUIDELINES:\n{copywriting_guidelines}\n"
            guidelines_section += "\n=== END GUIDELINES ===\n"

        system_prompt = f"""You are an email marketing strategist helping plan campaigns for {client_name}.
{guidelines_section}
CRITICAL: Before queuing any campaigns, you MUST use get_client_names to get the Client ID.
Use the Client ID (not Client Name) when calling queue_campaign and upload_campaigns.

Workflow:
1. Use get_client_names to get the Client ID for "{client_name}"
2. Use get_client_segments to see available audience segments
3. Use get_campaign_templates to see campaign types
4. Use company_background_search for brand voice and product info
5. Queue campaigns with queue_campaign using the Client ID
6. Review with view_campaign_queue
7. Upload all with upload_campaigns using the Client ID

You can also use WebSearch/WebFetch for marketing research.

Do not mention internal tools like Task or TodoWrite to the user."""

        # Configure options
        return ClaudeAgentOptions(
            mcp_servers={"chat-tools": tools_server},
            allowed_tools=allowed_tools,
            disallowed_tools=disallowed_tools,
            system_prompt=system_prompt,
            include_partial_messages=True,  # Enable real-time streaming of partial messages
        )

    async def connect(self, resume: Optional[str] = None):
        """Initialize and connect the Claude client.

        Args:
            resume: Optional session_id to resume a previous conversation
        """
        # Always create fresh options with current client context
        self.resume_session_id = resume
        options = self._create_options()

        # Add resume if provided
        if resume:
            from dataclasses import replace
            options = replace(options, resume=resume)

        self.client = ClaudeSDKClient(options=options)
        await self.client.connect()

    async def disconnect(self):
        """Disconnect the Claude client."""
        if self.client:
            await self.client.disconnect()
            self.client = None

    async def send_message(self, message: str) -> AsyncIterator[dict]:
        """
        Send a message to Claude and stream responses.

        Yields dictionaries with message data formatted for the frontend.
        """
        if not self.client:
            raise RuntimeError("Client not connected. Call connect() first.")

        # Send the message
        await self.client.query(message)

        # Stream responses
        async for msg in self.client.receive_response():
            yield self._format_message(msg)

    def _format_message(self, msg) -> dict:
        """Format a message for the frontend."""
        if isinstance(msg, UserMessage):
            return {
                "type": "user",
                "content": self._extract_text_content(msg.content),
                "timestamp": self._get_timestamp(),
            }

        elif isinstance(msg, SystemMessage):
            # Check if this is an init message with session_id
            print(f"🔍 SystemMessage received: subtype={getattr(msg, 'subtype', None)}, data={getattr(msg, 'data', None)}")
            if hasattr(msg, 'subtype') and msg.subtype == 'init':
                if hasattr(msg, 'data') and isinstance(msg.data, dict):
                    session_id = msg.data.get('session_id')
                    if session_id:
                        self.current_session_id = session_id
                        print(f"✅ Captured session_id: {session_id}")

            return {
                "type": "system",
                "content": str(msg),
                "session_id": self.current_session_id,
                "timestamp": self._get_timestamp(),
            }

        elif isinstance(msg, AssistantMessage):
            formatted = {
                "type": "assistant",
                "content": "",
                "tools_used": [],
                "timestamp": self._get_timestamp(),
            }

            for block in msg.content:
                if isinstance(block, TextBlock):
                    formatted["content"] += block.text
                elif isinstance(block, ToolUseBlock):
                    formatted["tools_used"].append(
                        {
                            "name": block.name,
                            "input": block.input,
                            "id": block.id,
                        }
                    )

            return formatted

        elif isinstance(msg, ResultMessage):
            return {
                "type": "result",
                "cost": msg.total_cost_usd,
                "duration_ms": msg.duration_ms,
                "is_error": msg.is_error,
                "timestamp": self._get_timestamp(),
            }

        elif isinstance(msg, StreamEvent):
            # Handle partial message updates from streaming
            event = msg.event
            event_type = event.get("type")

            # Handle text delta events
            if event_type == "content_block_delta":
                delta = event.get("delta", {})
                delta_type = delta.get("type")
                if delta_type == "text_delta":
                    return {
                        "type": "stream_text",
                        "content": delta.get("text", ""),
                        "timestamp": self._get_timestamp(),
                    }

            # Handle tool use start - let frontend know a tool is being used
            if event_type == "content_block_start":
                content_block = event.get("content_block", {})
                block_type = content_block.get("type")
                if block_type == "tool_use":
                    return {
                        "type": "tool_use_start",
                        "tool_name": content_block.get("name", "unknown"),
                        "tool_id": content_block.get("id", ""),
                        "timestamp": self._get_timestamp(),
                    }

            # Message boundaries - critical for post-tool streaming
            if event_type == "message_start":
                return {"type": "message_start", "timestamp": self._get_timestamp()}

            if event_type == "message_stop":
                return {"type": "message_stop", "timestamp": self._get_timestamp()}

            # Pass through other stream events (ignored by frontend)
            return {"type": "stream_event", "event_type": event_type}

        return {"type": "unknown", "content": str(msg)}

    def _extract_text_content(self, content) -> str:
        """Extract text content from message blocks."""
        text_parts = []
        for block in content:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
        return " ".join(text_parts)

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime

        return datetime.now().isoformat()


# Global client instance
chat_client = ChatClient()
