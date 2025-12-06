"""
Configuration for tools - loads from environment variables.

Required environment variables:
- SUPABASE_DB_URL: PostgreSQL connection string for Supabase
- OPENAI_API_KEY: OpenAI API key for embeddings
- GOOGLE_SERVICE_ACCOUNT_JSON: Google service account credentials
- GOOGLE_SPREADSHEET_ID: Google Sheets document ID
"""

import os
import json
import base64
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Tool configuration loaded from environment variables."""

    # Google Sheets config
    GOOGLE_SERVICE_ACCOUNT_JSON: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    GOOGLE_SPREADSHEET_ID: str = os.getenv(
        "GOOGLE_SPREADSHEET_ID", "10qfz5Ky2CiPU-Yr1UUooVZT6v5s8zaEC90_JQTCs7OY"
    )
    GOOGLE_SHEET_NAME: str = os.getenv("GOOGLE_SHEET_NAME", "Clients")

    @classmethod
    def get_google_credentials_dict(cls) -> dict | None:
        """Parse Google credentials from env var (base64, JSON string, or file path)."""
        value = cls.GOOGLE_SERVICE_ACCOUNT_JSON
        if not value:
            return None

        # Try base64 decode first
        try:
            decoded = base64.b64decode(value).decode('utf-8')
            return json.loads(decoded)
        except Exception:
            pass

        # Try parsing as JSON directly
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

        # Try reading as file path
        try:
            with open(value, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        return None

    @classmethod
    def validate_google_sheets(cls) -> bool:
        """Check if Google Sheets credentials are configured."""
        return bool(cls.GOOGLE_SERVICE_ACCOUNT_JSON and cls.GOOGLE_SPREADSHEET_ID)

    # Supabase/PostgreSQL config
    SUPABASE_DB_URL: str = os.getenv("SUPABASE_DB_URL", "")

    # OpenAI config (for embeddings)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # PGVector config - Company Background table
    PGVECTOR_TABLE_NAME: str = os.getenv("PGVECTOR_TABLE_NAME", "documents")
    PGVECTOR_CONTENT_COLUMN: str = os.getenv("PGVECTOR_CONTENT_COLUMN", "content")
    PGVECTOR_EMBEDDING_COLUMN: str = os.getenv("PGVECTOR_EMBEDDING_COLUMN", "embedding")
    PGVECTOR_METADATA_COLUMN: str = os.getenv("PGVECTOR_METADATA_COLUMN", "metadata")

    # Approved Copy table config
    APPROVED_COPY_TABLE_NAME: str = os.getenv("APPROVED_COPY_TABLE_NAME", "approved_copy")

    @classmethod
    def validate_pgvector(cls) -> bool:
        """Check if PGVector/Supabase credentials are configured."""
        return bool(cls.SUPABASE_DB_URL and cls.OPENAI_API_KEY)


config = Config()
