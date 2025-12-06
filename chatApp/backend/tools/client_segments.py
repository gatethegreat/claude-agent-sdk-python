"""
Google Sheets client segments tool.

Reads segment definitions from a Google Sheet to provide available
segments and their descriptions for use in marketing/automation workflows.
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
    "get_client_segments",
    (
        "Get a list of available segments and their descriptions. "
        "Use this tool to understand which customer/lead segments are available "
        "and when each segment should be used."
    ),
    {},  # No parameters required
)
async def get_client_segments(args: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch all segment definitions from Google Sheets.

    Returns segment names and their definitions to help understand
    which segments are available and when to use each one.
    """
    try:
        from .config import config

        # Connect to Google Sheets
        client = _get_gspread_client()
        spreadsheet = client.open_by_key(config.SEGMENT_DEFINITIONS_SPREADSHEET_ID)
        worksheet = spreadsheet.sheet1  # First sheet (Sheet1)

        # Get all records
        records = worksheet.get_all_records()

        if not records:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "No segment definitions found in the spreadsheet.",
                    }
                ]
            }

        # Format the response with segment name and definition
        segments_text = []
        for record in records:
            name = record.get("Name", "")
            definition = record.get("Definition", "")
            if name:
                segments_text.append(f"**{name}**\n{definition}")

        if not segments_text:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "No segments found with valid Name/Definition columns.",
                    }
                ]
            }

        result = f"Available Segments ({len(segments_text)} total):\n\n" + "\n\n".join(
            segments_text
        )

        return {"content": [{"type": "text", "text": result}]}

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
                    "text": f"Error fetching segment definitions: {str(e)}",
                }
            ],
            "is_error": True,
        }
