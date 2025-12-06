"""
Campaign queue and bulk upload tools.

Queue campaigns during planning, then bulk upload to Google Sheets.
"""

import time
import random
import string
import json
import os
from datetime import datetime
from typing import Any
from claude_agent_sdk import tool

# Persistent queue file path (in Docker volume)
QUEUE_FILE = os.environ.get("QUEUE_FILE_PATH", "/app/data/campaign_queues.json")


def _load_queues() -> dict[str, list[dict[str, Any]]]:
    """Load queues from JSON file."""
    try:
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ Error loading queue file: {e}")
    return {}


def _save_queues(queues: dict[str, list[dict[str, Any]]]) -> None:
    """Save queues to JSON file."""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
        with open(QUEUE_FILE, "w") as f:
            json.dump(queues, f, indent=2)
    except IOError as e:
        print(f"❌ Error saving queue file: {e}")


def _generate_campaign_id() -> str:
    """Generate unique campaign ID: CAMP-{timestamp}-{random}"""
    timestamp = int(time.time() * 1000)
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"CAMP-{timestamp}-{random_str}"


def _format_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to MM/DD/YYYY format."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%m/%d/%Y")
    except ValueError:
        return date_str


def _get_month(date_str: str) -> str:
    """Extract month name from YYYY-MM-DD date."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%B")
    except ValueError:
        return ""


@tool(
    "queue_campaign",
    (
        "Add a campaign to the upload queue for a specific client. "
        "IMPORTANT: Use get_client_names first to get the Client ID - do NOT use the client name. "
        "When done planning, call upload_campaigns with the client_id to send queued campaigns to Google Sheets. "
        "Each client has their own separate queue."
    ),
    {
        "type": "object",
        "properties": {
            "client_id": {"type": "string", "description": "Client ID (NOT client name) - get this from get_client_names tool"},
            "campaign_number": {"type": "integer", "description": "Sequential campaign number (1, 2, 3...)"},
            "idea_name": {"type": "string", "description": "Campaign name/title"},
            "campaign_date": {"type": "string", "description": "Send date in YYYY-MM-DD format"},
            "angle": {"type": "string", "description": "Campaign angle or hook"},
            "notes": {"type": "string", "description": "Additional notes or context"},
            "campaign_type": {"type": "string", "description": "Template type (e.g. Promotional, Educational-Content, High-Click, Fillers)"},
            "justification": {"type": "string", "description": "Why this campaign fits the strategy"},
            "campaign_channel": {"type": "string", "description": "Channel: Email or SMS"},
            "target_segments": {"type": "string", "description": "Target segment(s) for this campaign"},
            "featured_product": {"type": "string", "description": "Product to feature (optional)"},
        },
        "required": ["client_id", "campaign_number", "idea_name", "campaign_date", "campaign_type", "campaign_channel", "target_segments"],
    },
)
async def queue_campaign(args: dict[str, Any]) -> dict[str, Any]:
    """Add a campaign to the client-specific queue for bulk upload."""
    client_id = args["client_id"]
    print(f"📥 queue_campaign called: {args.get('idea_name')} for client {client_id}")

    # Load existing queues
    queues = _load_queues()

    # Initialize queue for this client if needed
    if client_id not in queues:
        queues[client_id] = []

    # Add to client's queue
    queues[client_id].append({
        "campaign_number": args["campaign_number"],
        "idea_name": args["idea_name"],
        "campaign_date": args["campaign_date"],
        "angle": args.get("angle", ""),
        "notes": args.get("notes", ""),
        "campaign_type": args["campaign_type"],
        "justification": args.get("justification", ""),
        "featured_product": args.get("featured_product", ""),
        "campaign_channel": args["campaign_channel"],
        "target_segments": args["target_segments"],
    })

    # Save to file
    _save_queues(queues)

    queue_size = len(queues[client_id])
    return {
        "content": [
            {
                "type": "text",
                "text": f"Campaign #{args['campaign_number']} '{args['idea_name']}' queued for {client_id}. Total in queue: {queue_size}",
            }
        ]
    }


@tool(
    "upload_campaigns",
    (
        "Upload all queued campaigns for a specific client to Google Sheets in a single batch. "
        "Call this after queuing all campaigns with queue_campaign."
    ),
    {
        "type": "object",
        "properties": {
            "client_id": {"type": "string", "description": "Client ID whose campaigns to upload"},
        },
        "required": ["client_id"],
    },
)
async def upload_campaigns(args: dict[str, Any]) -> dict[str, Any]:
    """Bulk upload all queued campaigns for a client to Google Sheets."""
    client_id = args["client_id"]

    # Load queues from file
    queues = _load_queues()
    client_queue = queues.get(client_id, [])

    print(f"📤 upload_campaigns called. Client: {client_id}, Queue size: {len(client_queue)}")

    if not client_queue:
        print(f"❌ Queue is empty for {client_id}!")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"No campaigns in queue for {client_id}. Use queue_campaign to add campaigns first.",
                }
            ],
            "is_error": True,
        }

    try:
        # Lazy import gspread
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        from .config import config

        print(f"🔑 Getting credentials...")
        creds_dict = config.get_google_credentials_dict()
        if not creds_dict:
            print("❌ No credentials found!")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Error: Google Sheets credentials not configured. "
                               "Set GOOGLE_SERVICE_ACCOUNT_JSON environment variable.",
                    }
                ],
                "is_error": True,
            }

        print(f"📊 Connecting to spreadsheet: {config.GOOGLE_SPREADSHEET_ID}")
        # Connect to Google Sheets
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(config.GOOGLE_SPREADSHEET_ID)
        print(f"📋 Opening worksheet: Campaigns")
        worksheet = spreadsheet.worksheet("Campaigns")

        # Build rows for bulk insert
        # Columns: A:Campaign Id, B:Approve/Request Changes, C:Change Notes, D:Campaign #,
        # E:Campaign Name, F:Campaign Date, G:Angle, H:Notes, I:Campaign Type, J:Justification,
        # K:Featured Product, L:Client Name, M:Linked Brief ID, N:Linked Copy ID, O:Created Time,
        # P:Campaign Process Step, Q:Month, R:Client ID, S:Campaign Channel, T:Raleon,
        # U:Where from, V:CTA Link, W:Segment
        rows = []
        for campaign in client_queue:
            row = [
                _generate_campaign_id(),  # A: Campaign Id
                "Pending",  # B: Approve/Request Changes
                "",  # C: Change Notes
                campaign["campaign_number"],  # D: Campaign #
                campaign["idea_name"],  # E: Campaign Name
                _format_date(campaign["campaign_date"]),  # F: Campaign Date
                campaign["angle"],  # G: Angle
                campaign["notes"],  # H: Notes
                campaign["campaign_type"],  # I: Campaign Type
                campaign["justification"],  # J: Justification
                campaign["featured_product"],  # K: Featured Product
                "",  # L: Client Name (blank as per original)
                "",  # M: Linked Brief ID
                "",  # N: Linked Copy ID
                datetime.now().isoformat(),  # O: Created Time
                "Pending Review",  # P: Campaign Process Step
                _get_month(campaign["campaign_date"]),  # Q: Month
                client_id,  # R: Client ID
                campaign["campaign_channel"],  # S: Campaign Channel
                "",  # T: Raleon
                "Campaign Agent",  # U: Where from
                "",  # V: CTA Link
                campaign["target_segments"],  # W: Segment
            ]
            rows.append(row)

        # Bulk append all rows
        print(f"📝 Appending {len(rows)} rows to sheet...")
        print(f"📝 First row sample: {rows[0][:5]}...")  # Show first 5 columns of first row
        # Use INSERT_ROWS to ensure new rows are inserted, not overwritten
        result = worksheet.append_rows(
            rows,
            value_input_option="USER_ENTERED",
            insert_data_option="INSERT_ROWS"
        )
        print(f"✅ Append result: {result}")

        # Clear the client's queue and save
        count = len(client_queue)
        queues[client_id] = []
        _save_queues(queues)

        print(f"✅ Successfully uploaded {count} campaigns for {client_id}!")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Successfully uploaded {count} campaigns for {client_id} to Google Sheets.",
                }
            ]
        }

    except Exception as e:
        print(f"❌ Error uploading: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error uploading campaigns: {str(e)}",
                }
            ],
            "is_error": True,
        }


@tool(
    "view_campaign_queue",
    "View all campaigns currently in the queue for a specific client. Use to review before uploading.",
    {
        "type": "object",
        "properties": {
            "client_id": {"type": "string", "description": "Client ID whose queue to view"},
        },
        "required": ["client_id"],
    },
)
async def view_campaign_queue(args: dict[str, Any]) -> dict[str, Any]:
    """View the campaign queue for a specific client."""
    client_id = args["client_id"]
    queues = _load_queues()
    client_queue = queues.get(client_id, [])

    if not client_queue:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Queue is empty for {client_id}. Use queue_campaign to add campaigns.",
                }
            ]
        }

    lines = [f"Campaign Queue for {client_id} ({len(client_queue)} campaigns):"]
    for campaign in client_queue:
        lines.append(
            f"  #{campaign['campaign_number']}: {campaign['idea_name']} - "
            f"{campaign['campaign_date']} - {campaign['campaign_type']} - {campaign['target_segments']}"
        )

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


@tool(
    "clear_campaign_queue",
    "Clear all campaigns from the queue for a specific client without uploading. Use if you need to start over.",
    {
        "type": "object",
        "properties": {
            "client_id": {"type": "string", "description": "Client ID whose queue to clear"},
        },
        "required": ["client_id"],
    },
)
async def clear_campaign_queue(args: dict[str, Any]) -> dict[str, Any]:
    """Clear the campaign queue for a specific client."""
    client_id = args["client_id"]

    # Load, clear, and save
    queues = _load_queues()
    client_queue = queues.get(client_id, [])
    count = len(client_queue)
    queues[client_id] = []
    _save_queues(queues)

    return {
        "content": [
            {
                "type": "text",
                "text": f"Cleared {count} campaigns from {client_id}'s queue." if count > 0 else f"Queue was already empty for {client_id}.",
            }
        ]
    }
