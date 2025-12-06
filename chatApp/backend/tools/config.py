"""
Configuration for tools - loads from environment variables.

Required environment variables:
- GOOGLE_SERVICE_ACCOUNT_JSON: JSON content of service account (as string) OR path to file
- GOOGLE_SPREADSHEET_ID: The Google Sheets document ID
- SUPABASE_DB_URL: PostgreSQL connection string for Supabase
- OPENAI_API_KEY: OpenAI API key for embeddings
"""

import os
import json
import base64
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Tool configuration loaded from environment variables."""

    # Google Sheets config - can be base64-encoded JSON, JSON content, or file path
    GOOGLE_SERVICE_ACCOUNT_JSON: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

    @classmethod
    def get_google_credentials_dict(cls) -> dict | None:
        """Parse Google credentials from env var (base64, JSON string, or file path)."""
        value = cls.GOOGLE_SERVICE_ACCOUNT_JSON
        if not value:
            return None

        # Try base64 decode first (recommended for Docker)
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
    GOOGLE_SPREADSHEET_ID: str = os.getenv(
        "GOOGLE_SPREADSHEET_ID", "10qfz5Ky2CiPU-Yr1UUooVZT6v5s8zaEC90_JQTCs7OY"
    )
    GOOGLE_SHEET_NAME: str = os.getenv("GOOGLE_SHEET_NAME", "Clients")

    # Segment Definitions spreadsheet
    SEGMENT_DEFINITIONS_SPREADSHEET_ID: str = os.getenv(
        "SEGMENT_DEFINITIONS_SPREADSHEET_ID", "1C78auIXB0GfWtj58w50btDeTLbIcsaEsiQ_fyZ9BgWo"
    )

    # Supabase/PostgreSQL config
    SUPABASE_DB_URL: str = os.getenv("SUPABASE_DB_URL", "")

    # OpenAI config (for embeddings)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # PGVector config
    PGVECTOR_TABLE_NAME: str = os.getenv("PGVECTOR_TABLE_NAME", "documents")
    PGVECTOR_CONTENT_COLUMN: str = os.getenv("PGVECTOR_CONTENT_COLUMN", "content")
    PGVECTOR_EMBEDDING_COLUMN: str = os.getenv("PGVECTOR_EMBEDDING_COLUMN", "embedding")
    PGVECTOR_METADATA_COLUMN: str = os.getenv("PGVECTOR_METADATA_COLUMN", "metadata")

    @classmethod
    def validate_google_sheets(cls) -> bool:
        """Check if Google Sheets credentials are configured."""
        return bool(cls.GOOGLE_SERVICE_ACCOUNT_JSON and cls.GOOGLE_SPREADSHEET_ID)

    @classmethod
    def validate_pgvector(cls) -> bool:
        """Check if PGVector/Supabase credentials are configured."""
        return bool(cls.SUPABASE_DB_URL and cls.OPENAI_API_KEY)


config = Config()
