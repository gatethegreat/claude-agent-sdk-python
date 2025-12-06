# Claude SDK Session Resume Issue

## Summary

When attempting to resume a previous conversation after a container restart, the Claude SDK fails with "No conversation found" errors. Users can see their past messages (stored in our database), but Claude has no memory of the conversation when they try to continue it.

## Current Behavior

1. User opens a past conversation → UI loads messages from our SQLite database ✅
2. User sends a new message → Backend attempts to resume Claude SDK session ❌
3. Resume fails with error: `No conversation found with session ID: <uuid>`
4. Fallback starts a fresh Claude session, but Claude has no context of previous messages

## Error Logs

```
No conversation found with session ID: 6e43e54d-54ff-4817-9d70-8271316ebca2
Fatal error in message reader: Command failed with exit code 1 (exit code: 1)
Error output: Check stderr output for details

🔄 Attempting to resume SDK session: 6e43e54d-54ff-4817-9d70-8271316ebca2
⚠️ Resume failed, starting fresh: Control request timeout: initialize
📋 Using existing DB session: e4b1c2c2-cb0a-4470-875b-7121c4b8c6ea
✅ Claude client connected for: Bargain Max
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Our Application                          │
├─────────────────────────────────────────────────────────────┤
│  SQLite Database (/app/data/chat_sessions.db)               │
│  - Stores: session metadata, message history                 │
│  - Persists across container restarts ✅                     │
│  - Used for: displaying past conversations in UI             │
├─────────────────────────────────────────────────────────────┤
│  Claude SDK Client (claude_agent_sdk)                        │
│  - Creates sessions with unique sdk_session_id               │
│  - We store sdk_session_id in our database                   │
│  - On resume: pass sdk_session_id to SDK to continue         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Claude's Infrastructure                    │
├─────────────────────────────────────────────────────────────┤
│  Session Storage (Anthropic-managed)                         │
│  - Sessions appear to expire/become invalid                  │
│  - After container restart, old session IDs not recognized   │
│  - Returns: "No conversation found with session ID"          │
└─────────────────────────────────────────────────────────────┘
```

## The Problem

The Claude SDK's `resume` parameter expects a valid `session_id` that exists on Claude's infrastructure. However:

1. **Sessions may have a TTL** - Claude's sessions might expire after a period of inactivity
2. **Sessions may not persist** - When our container restarts, Claude's session state may be lost
3. **Session IDs become stale** - The `sdk_session_id` we stored is no longer valid on Claude's end

## Code Flow

```python
# In main.py - WebSocket handler
if resume_sdk_session_id:
    try:
        # This fails with "No conversation found"
        await chat_client.connect(resume=resume_sdk_session_id)
    except Exception as e:
        # Falls back to fresh session - Claude has no memory
        await chat_client.connect()
```

```python
# In claude_client.py
async def connect(self, resume: Optional[str] = None):
    options = self._create_options()
    if resume:
        options = replace(options, resume=resume)  # Add resume param

    self.client = ClaudeSDKClient(options=options)
    await self.client.connect()  # This throws if session doesn't exist
```

## Questions for Claude SDK Team

1. **What is the TTL for SDK sessions?** How long do they remain valid?

2. **Do sessions persist across API restarts?** Or are they only valid for the lifetime of a single connection?

3. **Is there a way to check if a session is still valid** before attempting to resume?

4. **What's the recommended pattern for long-term conversation persistence?** Should we:
   - Re-inject message history into a new session?
   - Use a different API for persistent conversations?
   - Something else?

5. **What does "No conversation found" specifically mean?** Is the session:
   - Expired due to time?
   - Deleted due to our container restart?
   - Never persisted on Claude's end in the first place?

## Potential Workarounds

### Option 1: Inject Message History (Recommended)
When resume fails, fetch messages from our database and include them in the system prompt or as initial context:

```python
if resume_failed:
    messages = db.get_messages(session_id)
    history = format_as_context(messages)
    # Include history in system prompt so Claude "knows" what was discussed
```

### Option 2: Accept Limitation
Document that conversations can only be resumed within a single container lifecycle. After restart, Claude starts fresh but UI still shows history.

### Option 3: Different SDK Usage
Investigate if there's a different pattern (e.g., using the Messages API directly with conversation history) that provides more reliable persistence.

## Environment

- Claude SDK: `claude_agent_sdk` (via `@anthropic-ai/claude-code` CLI)
- Container: Docker with Python 3.11
- Session storage: SQLite in Docker volume (`/app/data/`)
- Deployment: AWS EC2, containers restart on each deploy
