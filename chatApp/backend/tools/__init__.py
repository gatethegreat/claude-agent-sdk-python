"""
Custom MCP tools for the chat application.

Tools are organized in this folder by category/purpose.
"""

from .campaign_templates import get_campaign_templates
from .campaign_upload import clear_campaign_queue, queue_campaign, upload_campaigns, view_campaign_queue
from .client_lookup import get_client_names
from .client_segments import get_client_segments
from .knowledge_search import company_background_search

# Export all tools for use with Claude SDK
ALL_TOOLS = [
    clear_campaign_queue,
    get_campaign_templates,
    get_client_names,
    get_client_segments,
    queue_campaign,
    upload_campaigns,
    view_campaign_queue,
    company_background_search,
]

__all__ = [
    "ALL_TOOLS",
    "clear_campaign_queue",
    "get_campaign_templates",
    "get_client_names",
    "get_client_segments",
    "queue_campaign",
    "upload_campaigns",
    "view_campaign_queue",
    "company_background_search",
]
