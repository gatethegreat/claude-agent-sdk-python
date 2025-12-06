"""
Fetch client guidelines (discount/offer and copywriting) from Google Sheets.

Used to provide client-specific context to the AI system prompt.
"""

from typing import Optional


def _get_gspread_client():
    """Lazily initialize and return gspread client."""
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    from .config import config

    creds_dict = config.get_google_credentials_dict()
    if not creds_dict:
        raise ValueError(
            "Google Sheets credentials not configured. "
            "Set GOOGLE_SERVICE_ACCOUNT_JSON environment variable."
        )

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)


def get_client_guidelines(client_name: str) -> dict[str, Optional[str]]:
    """
    Fetch discount and copywriting guidelines for a specific client.

    Args:
        client_name: The name of the client to look up

    Returns:
        Dictionary with 'discount_guidelines' and 'copywriting_guidelines' keys.
        Values are None if not found or empty.
    """
    try:
        from .config import config

        client = _get_gspread_client()
        spreadsheet = client.open_by_key(config.GOOGLE_SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(config.GOOGLE_SHEET_NAME)

        # Get all records
        records = worksheet.get_all_records()

        # Find the matching client (case-insensitive)
        for record in records:
            record_name = record.get("Client Name", "")
            if record_name.lower() == client_name.lower():
                discount = record.get("Discount/Offer Guidelines", "")
                copywriting = record.get("Copywriting Guidelines", "")

                return {
                    "discount_guidelines": discount if discount else None,
                    "copywriting_guidelines": copywriting if copywriting else None,
                }

        # Client not found
        return {
            "discount_guidelines": None,
            "copywriting_guidelines": None,
        }

    except Exception as e:
        print(f"⚠️ Error fetching client guidelines: {e}")
        return {
            "discount_guidelines": None,
            "copywriting_guidelines": None,
        }
