"""Calculator MCP tools for the test agent."""

from .calculator import add, multiply, divide

ALL_TOOLS = [
    add,
    multiply,
    divide,
]

__all__ = ["ALL_TOOLS", "add", "multiply", "divide"]
