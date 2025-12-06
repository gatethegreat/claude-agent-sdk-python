"""FastAPI server for copywriting agent with WebSocket streaming."""

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock
from claude_agent_sdk.types import StreamEvent
from claude_client import CopywritingClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print("Copywriting Agent Server starting...")
    yield
    print("Copywriting Agent Server shutting down...")


app = FastAPI(
    title="Copywriting Agent API",
    description="A Claude agent for creating marketing copy",
    lifespan=lifespan,
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "copywriting-agent"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with copywriting agent."""
    await websocket.accept()
    client: CopywritingClient | None = None
    sdk_session_id: str | None = None

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "connect":
                # Initialize the copywriting client
                resume_id = message.get("resume_sdk_session_id")
                client_name = message.get("client_name")
                print(f"[DEBUG] Connect request - client_name: {client_name}, resume_id: {resume_id}")

                client = CopywritingClient()
                if client_name:
                    client.set_client_name(client_name)

                print("[DEBUG] Connecting to Claude SDK...")
                await client.connect(resume_session_id=resume_id)
                print("[DEBUG] Claude SDK connected successfully")
                await websocket.send_json({
                    "type": "connected",
                    "message": "Copywriting agent connected",
                    "client_name": client_name,
                })

            elif msg_type == "message":
                if not client:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Not connected. Send connect message first.",
                    })
                    continue

                content = message.get("content", "")
                if not content:
                    continue

                print(f"[DEBUG] User message: {content[:100]}...")

                # Stream the response
                full_text = ""
                tools_used = []

                async for msg in client.send_message(content):
                    print(f"[DEBUG] Received message type: {type(msg).__name__}")
                    if isinstance(msg, StreamEvent):
                        # Handle streaming events (proper delta handling)
                        event = msg.event
                        event_type = event.get("type")

                        # Handle text delta events
                        if event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            delta_type = delta.get("type")
                            if delta_type == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    full_text += text
                                    await websocket.send_json({
                                        "type": "stream_text",
                                        "content": text,
                                    })

                        # Handle tool use start
                        elif event_type == "content_block_start":
                            content_block = event.get("content_block", {})
                            block_type = content_block.get("type")
                            if block_type == "tool_use":
                                tool_name = content_block.get("name", "unknown")
                                tool_id = content_block.get("id", "")
                                if tool_name not in tools_used:
                                    tools_used.append(tool_name)
                                    await websocket.send_json({
                                        "type": "tool_use_start",
                                        "tool_name": tool_name,
                                        "tool_id": tool_id,
                                    })

                    elif isinstance(msg, AssistantMessage):
                        # Final assistant message - extract complete text
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                full_text = block.text
                            elif isinstance(block, ToolUseBlock):
                                if block.name not in tools_used:
                                    tools_used.append(block.name)

                    elif isinstance(msg, ResultMessage):
                        # Response complete
                        sdk_session_id = client.get_session_id()

                # Send final message with full content
                await websocket.send_json({
                    "type": "assistant",
                    "content": full_text,
                    "tools_used": tools_used,
                    "sdk_session_id": sdk_session_id,
                })

            elif msg_type == "disconnect":
                break

    except WebSocketDisconnect:
        print("[DEBUG] WebSocket disconnected")
    except Exception as e:
        import traceback
        print(f"[ERROR] WebSocket error: {e}")
        traceback.print_exc()
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
        except Exception:
            pass
    finally:
        if client:
            await client.disconnect()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
