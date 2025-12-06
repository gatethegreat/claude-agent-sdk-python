"""
Custom MCP tools for the copywriting agent.

Tools:
- get_client_names: Get list of active clients (use FIRST)
- company_background_search: Search company knowledge base
- approved_copy_search: Search approved copy examples
"""

from .client_lookup import get_client_names
from .knowledge_search import company_background_search
from .approved_copy import approved_copy_search

# Export all tools for use with Claude SDK
ALL_TOOLS = [
    get_client_names,
    company_background_search,
    approved_copy_search,
]

__all__ = [
    "ALL_TOOLS",
    "get_client_names",
    "company_background_search",
    "approved_copy_search",
]
