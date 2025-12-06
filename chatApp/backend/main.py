"""
FastAPI backend for Claude chat application.

Provides WebSocket endpoint for real-time chat with Claude.
"""

import asyncio
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from pydantic import BaseModel
import uvicorn
from claude_client import ChatClient as ClaudeChatClient
from database import db
from tools.client_guidelines import get_client_guidelines

app = FastAPI(title="Claude Chat API", version="1.0.0")


# Custom CORS middleware that definitely works
class CORSMiddlewareCustom(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Handle preflight OPTIONS request
        if request.method == "OPTIONS":
            return StarletteResponse(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                    "Access-Control-Max-Age": "86400",
                }
            )

        # Process the actual request
        response = await call_next(request)

        # Add CORS headers to all responses
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"

        return response


app.add_middleware(CORSMiddlewareCustom)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "service": "Claude Chat API",
        "endpoints": {
            "websocket": "/ws",
            "health": "/health",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# Session Management API Endpoints

class SessionCreate(BaseModel):
    """Request model for creating a session."""
    title: str = "New Chat"


class SessionUpdate(BaseModel):
    """Request model for updating a session."""
    title: str


@app.get("/api/sessions")
async def list_sessions(client: str = None):
    """List all sessions ordered by most recent, optionally filtered by client."""
    sessions = db.list_sessions(client_name=client)
    return {"sessions": sessions}


@app.post("/api/sessions")
async def create_session(data: SessionCreate):
    """Create a new session (placeholder - actual session_id comes from SDK)."""
    import uuid
    temp_session_id = f"temp-{uuid.uuid4()}"
    session = db.create_session(session_id=temp_session_id, title=data.title)
    return session


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a specific session by ID."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.patch("/api/sessions/{session_id}")
async def update_session(session_id: str, data: SessionUpdate):
    """Update a session (e.g., rename)."""
    success = db.update_session(session_id, title=data.title)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    success = db.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}


@app.get("/api/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    """Get all messages for a session."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = db.get_messages(session_id)
    return {"messages": messages}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat with Claude.

    Protocol:
    - Client sends: {"type": "connect", "client_context": {...}, "resume_sdk_session_id": "optional"}
    - Client sends: {"type": "message", "content": "user message here"}
    - Server streams: {"type": "assistant|user|result", ...message data...}
    """
    await websocket.accept()
    print("🔌 WebSocket connection established")

    current_db_session_id = None
    client_context = None
    chat_client = None  # Create a new client for each connection
    captured_sdk_session_id = None  # The real SDK session ID for resumption
    # Track accumulated content for saving on disconnect
    pending_accumulated_content = ""
    pending_accumulated_tools = []
    pending_response_timestamp = None

    try:
        # Send connection success message immediately
        await websocket.send_json(
            {
                "type": "system",
                "content": "Connected. Waiting for client context...",
            }
        )

        # Main message loop
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "connect":
                # Handle connect message with client context
                new_client_context = message_data.get("client_context")
                resume_sdk_session_id = message_data.get("resume_sdk_session_id")
                resume_db_session_id = message_data.get("resume_db_session_id")

                if new_client_context:
                    client_context = new_client_context
                    client_name = client_context.get('clientName', 'Unknown')

                    # Fetch client guidelines from Google Sheets
                    guidelines = get_client_guidelines(client_name)
                    client_context['discountGuidelines'] = guidelines.get('discount_guidelines')
                    client_context['copywritingGuidelines'] = guidelines.get('copywriting_guidelines')
                    print(f"📋 Fetched guidelines for {client_name}: discount={bool(guidelines.get('discount_guidelines'))}, copywriting={bool(guidelines.get('copywriting_guidelines'))}")

                    # Create a fresh Claude client for this connection
                    if chat_client:
                        try:
                            await chat_client.disconnect()
                        except:
                            pass

                    chat_client = ClaudeChatClient()
                    chat_client.set_client_context(client_context)

                    # If resuming a session, use the SDK session ID
                    if resume_sdk_session_id:
                        print(f"🔄 Attempting to resume SDK session: {resume_sdk_session_id}")
                        try:
                            # Add timeout to prevent hanging on invalid session
                            await asyncio.wait_for(
                                chat_client.connect(resume=resume_sdk_session_id),
                                timeout=10.0
                            )
                            captured_sdk_session_id = resume_sdk_session_id
                            current_db_session_id = resume_db_session_id
                            print(f"✅ Resumed session: db={current_db_session_id}")

                            # Notify frontend that we resumed this session
                            await websocket.send_json({
                                "type": "session_resumed",
                                "db_session_id": current_db_session_id,
                                "sdk_session_id": captured_sdk_session_id,
                            })
                        except asyncio.TimeoutError:
                            print(f"⚠️ Resume timed out, starting fresh")
                            await chat_client.connect()
                            if resume_db_session_id:
                                current_db_session_id = resume_db_session_id
                                print(f"📋 Using existing DB session: {current_db_session_id}")
                                try:
                                    await websocket.send_json({
                                        "type": "session_resumed",
                                        "db_session_id": current_db_session_id,
                                        "sdk_session_id": None,
                                        "note": "SDK session timed out, started fresh"
                                    })
                                except Exception:
                                    pass  # Connection already closed
                        except Exception as e:
                            print(f"⚠️ Resume failed, starting fresh: {e}")
                            await chat_client.connect()
                            # Still use the existing DB session even if SDK resume failed
                            if resume_db_session_id:
                                current_db_session_id = resume_db_session_id
                                print(f"📋 Using existing DB session: {current_db_session_id}")
                                try:
                                    await websocket.send_json({
                                        "type": "session_resumed",
                                        "db_session_id": current_db_session_id,
                                        "sdk_session_id": None,  # SDK session is fresh
                                        "note": "SDK session expired, started fresh but keeping conversation history"
                                    })
                                except Exception:
                                    pass  # Connection already closed
                    else:
                        await chat_client.connect()

                    print(f"✅ Claude client connected for: {client_name}")

                    await websocket.send_json({
                        "type": "system",
                        "content": f"Connected to Claude. Ready to chat about {client_name}!",
                    })

            elif message_data.get("type") == "message":
                user_message = message_data.get("content", "")

                if not user_message.strip():
                    continue

                if not chat_client:
                    await websocket.send_json({
                        "type": "error",
                        "content": "Not connected to Claude. Please refresh the page.",
                    })
                    continue

                print(f"📨 Received: {user_message[:50]}...")

                # Echo user message back
                user_timestamp = datetime.now().isoformat()
                await websocket.send_json(
                    {
                        "type": "user",
                        "content": user_message,
                        "timestamp": user_timestamp,
                    }
                )

                # Create session IMMEDIATELY on first message
                if not current_db_session_id:
                    import uuid
                    our_session_id = f"chat-{uuid.uuid4()}"
                    # Format: "Nov 26 - First few words of message"
                    date_prefix = datetime.now().strftime("%b %d")
                    message_preview = user_message[:30].strip()
                    if len(user_message) > 30:
                        message_preview += "..."
                    title = f"{date_prefix} - {message_preview}"
                    current_client_name = client_context.get("clientName") if client_context else None

                    session = db.create_session(
                        session_id=our_session_id,
                        title=title,
                        client_name=current_client_name
                    )
                    current_db_session_id = session["id"]
                    print(f"📝 Created session: {current_db_session_id} for client: {current_client_name}")

                    db.store_message(
                        session_id=current_db_session_id,
                        type="user",
                        content=user_message,
                        timestamp=user_timestamp,
                    )

                    await websocket.send_json({
                        "type": "session_created",
                        "db_session_id": current_db_session_id,
                        "title": title,
                        "client_name": current_client_name,
                    })
                else:
                    db.store_message(
                        session_id=current_db_session_id,
                        type="user",
                        content=user_message,
                        timestamp=user_timestamp,
                    )

                # Stream Claude's response
                # Reset accumulators for this response
                pending_accumulated_content = ""
                pending_accumulated_tools = []
                pending_response_timestamp = None

                try:
                    async for response in chat_client.send_message(user_message):
                        await websocket.send_json(response)

                        # Capture SDK session_id from init message
                        if response.get("type") == "system" and response.get("session_id"):
                            new_sdk_session_id = response["session_id"]
                            if new_sdk_session_id != captured_sdk_session_id:
                                captured_sdk_session_id = new_sdk_session_id
                                print(f"🔗 Captured SDK session_id: {captured_sdk_session_id}")

                                # Store SDK session ID in database for future resumption
                                if current_db_session_id:
                                    db.update_session(
                                        current_db_session_id,
                                        sdk_session_id=captured_sdk_session_id
                                    )
                                    print(f"💾 Stored SDK session_id in database")

                                    # Send to frontend so it knows the SDK session ID
                                    await websocket.send_json({
                                        "type": "sdk_session_id",
                                        "sdk_session_id": captured_sdk_session_id,
                                    })

                        # Accumulate streamed text
                        if response.get("type") == "stream_text":
                            pending_accumulated_content += response.get("content", "")
                            if not pending_response_timestamp:
                                pending_response_timestamp = response.get("timestamp")

                        # Accumulate tool uses
                        if response.get("type") == "tool_use_start":
                            pending_accumulated_tools.append({
                                "name": response.get("tool_name"),
                                "id": response.get("tool_id"),
                            })

                        # Final assistant message - use this as the complete content
                        if response.get("type") == "assistant" and current_db_session_id:
                            final_content = response.get("content", "") or pending_accumulated_content
                            final_tools = response.get("tools_used") or pending_accumulated_tools

                            preview = final_content[:100]
                            db.update_session(
                                current_db_session_id,
                                last_message_preview=preview,
                                increment_message_count=True
                            )

                            db.store_message(
                                session_id=current_db_session_id,
                                type="assistant",
                                content=final_content,
                                tools_used=final_tools if final_tools else None,
                                timestamp=response.get("timestamp") or pending_response_timestamp,
                            )
                            # Clear accumulator after saving
                            pending_accumulated_content = ""
                            pending_accumulated_tools = []

                except Exception as e:
                    print(f"❌ Error processing message: {e}")
                    # Save any accumulated content before the error
                    if pending_accumulated_content and current_db_session_id:
                        print(f"💾 Saving partial message ({len(pending_accumulated_content)} chars)")
                        db.store_message(
                            session_id=current_db_session_id,
                            type="assistant",
                            content=pending_accumulated_content,
                            tools_used=pending_accumulated_tools if pending_accumulated_tools else None,
                            timestamp=pending_response_timestamp or datetime.now().isoformat(),
                        )
                        pending_accumulated_content = ""
                        pending_accumulated_tools = []
                    await websocket.send_json(
                        {
                            "type": "error",
                            "content": f"Error: {str(e)}",
                        }
                    )

            elif message_data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        print("🔌 WebSocket disconnected")
        # Don't save partial messages - they cause duplicates when user returns
        # The message will be lost, but that's better than duplicate/corrupted messages

    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        # Don't save partial messages on error - they cause duplicates
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "content": f"Server error: {str(e)}",
                }
            )
        except:
            pass

    finally:
        # Clean up: disconnect Claude client for this connection
        if chat_client:
            try:
                await chat_client.disconnect()
            except Exception as e:
                print(f"⚠️ Error disconnecting client: {e}")
        print("🔌 Connection closed")


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    print("🚀 Starting Claude Chat API server...")
    print("📡 WebSocket endpoint: ws://localhost:8000/ws")
    print("🌐 Health check: http://localhost:8000/health")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    print("👋 Shutting down Claude Chat API server...")


if __name__ == "__main__":
    print("=" * 60)
    print("🤖 Claude Chat API Server")
    print("=" * 60)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
