"""
Google Sheets campaign templates tool.

Reads campaign template definitions from a Google Sheet to provide
available templates and their details for campaign planning.
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
    "get_campaign_templates",
    (
        "Get a list of all available campaign templates and their campaign type. "
        "Returns template names, campaign types, descriptions, recommended segments, "
        "and revenue potential to help plan marketing campaigns."
    ),
    {},  # No parameters required
)
async def get_campaign_templates(args: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch all campaign templates from Google Sheets.

    Returns template details including name, campaign type, description,
    recommended segments, and revenue potential.
    """
    try:
        from .config import config

        # Connect to Google Sheets
        client = _get_gspread_client()
        spreadsheet = client.open_by_key(config.GOOGLE_SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet("Campaign Templates")

        # Get all records
        records = worksheet.get_all_records()

        if not records:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "No campaign templates found in the spreadsheet.",
                    }
                ]
            }

        # Filter for active templates and format output
        templates_text = []
        for record in records:
            # Skip inactive templates
            is_active = record.get("is_active", "")
            if is_active and str(is_active).lower() not in ["checked", "true", "yes", "1"]:
                continue

            name = record.get("name", "")
            campaign_type = record.get("Campaign Type", "")
            description = record.get("Description (from Campaign Type)", "")
            recommended_segments = record.get("Recommended Segments (from Campaign Type)", "")
            revenue_potential = record.get("revenue_potential", "")
            frequency = record.get("frequency", "")

            if name:
                template_info = f"**{name}** ({campaign_type})"
                if frequency:
                    template_info += f"\nFrequency: {frequency}"
                if description:
                    template_info += f"\nDescription: {description}"
                if recommended_segments:
                    template_info += f"\nRecommended Segments: {recommended_segments}"
                if revenue_potential:
                    # Clean up revenue_potential if it's a JSON array
                    if isinstance(revenue_potential, str) and revenue_potential.startswith("["):
                        revenue_potential = revenue_potential.strip('[]"')
                    template_info += f"\nRevenue Potential: {revenue_potential}"
                templates_text.append(template_info)

        if not templates_text:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "No active campaign templates found.",
                    }
                ]
            }

        result = f"Available Campaign Templates ({len(templates_text)} total):\n\n" + "\n\n---\n\n".join(
            templates_text
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
                    "text": f"Error fetching campaign templates: {str(e)}",
                }
            ],
            "is_error": True,
        }
