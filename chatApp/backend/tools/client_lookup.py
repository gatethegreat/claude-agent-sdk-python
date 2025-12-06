"""
Google Sheets client lookup tool.

Reads client names from a Google Sheet to help verify correct spelling
before using other tools that require client name as a parameter.
"""

from typing import Any
from claude_agent_sdk import tool

# Google Sheets dependencies - import lazily to avoid startup errors
gspread = None
ServiceAccountCredentials = None


def _get_gspread_client():
    """Lazily initialize and return gspread client."""
    global gspread, ServiceAccountCredentials

    if gspread is None:
        import gspread as _gspread
        from oauth2client.service_account import (
            ServiceAccountCredentials as _ServiceAccountCredentials,
        )

        gspread = _gspread
        ServiceAccountCredentials = _ServiceAccountCredentials

    from .config import config

    creds_dict = config.get_google_credentials_dict()
    if not creds_dict:
        raise ValueError(
            "Google Sheets credentials not configured. "
            "Set GOOGLE_SERVICE_ACCOUNT_JSON environment variable "
            "(JSON content or file path)."
        )

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)


@tool(
    "get_client_names",
    (
        "Read all active clients with their Client ID and Client Name. "
        "IMPORTANT: Use this tool to get the Client ID before queuing campaigns. "
        "The queue_campaign tool requires the Client ID (not Client Name). "
        "Returns Client ID and Client Name for all active clients."
    ),
    {},  # No parameters required
)
async def get_client_names(args: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch all active clients with their IDs from Google Sheets.

    This tool reads from the Clients sheet and returns Client ID and Client Name
    where Status = "Active". The Client ID is required for queuing campaigns.
    """
    try:
        from .config import config

        # Connect to Google Sheets
        client = _get_gspread_client()
        spreadsheet = client.open_by_key(config.GOOGLE_SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(config.GOOGLE_SHEET_NAME)

        # Get all records
        records = worksheet.get_all_records()

        # Filter for active clients and extract name + ID
        active_clients = [
            {
                "client_id": record.get("Client ID", ""),
                "client_name": record.get("Client Name", "")
            }
            for record in records
            if record.get("Status", "").lower() == "active"
            and record.get("Client Name")
        ]

        if not active_clients:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "No active clients found in the spreadsheet.",
                    }
                ]
            }

        # Format the response with both ID and Name
        client_list = "\n".join(
            f"• {c['client_name']} (ID: {c['client_id']})"
            for c in sorted(active_clients, key=lambda x: x['client_name'])
        )
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Active Clients ({len(active_clients)} total):\n\n{client_list}\n\nUse the Client ID (not name) when queuing campaigns.",
                }
            ]
        }

    except FileNotFoundError:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Error: Google service account JSON file not found. "
                        "Please check GOOGLE_SERVICE_ACCOUNT_JSON path."
                    ),
                }
            ],
            "is_error": True,
        }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error fetching client names: {str(e)}",
                }
            ],
            "is_error": True,
        }
