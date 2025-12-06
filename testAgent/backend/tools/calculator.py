"""Calculator tools: add, multiply, divide."""

from typing import Any
from claude_agent_sdk import tool


@tool(
    name="add",
    description="Add two numbers together. Returns the sum of a and b.",
    input_schema={
        "type": "object",
        "properties": {
            "a": {"type": "number", "description": "First number"},
            "b": {"type": "number", "description": "Second number"},
        },
        "required": ["a", "b"],
    },
)
async def add(args: dict[str, Any]) -> dict[str, Any]:
    """Add two numbers."""
    a = args.get("a")
    b = args.get("b")

    if a is None or b is None:
        return {
            "content": [{"type": "text", "text": "Error: Both 'a' and 'b' are required"}],
            "is_error": True,
        }

    result = a + b
    return {
        "content": [{"type": "text", "text": f"{a} + {b} = {result}"}],
    }


@tool(
    name="multiply",
    description="Multiply two numbers together. Returns the product of a and b.",
    input_schema={
        "type": "object",
        "properties": {
            "a": {"type": "number", "description": "First number"},
            "b": {"type": "number", "description": "Second number"},
        },
        "required": ["a", "b"],
    },
)
async def multiply(args: dict[str, Any]) -> dict[str, Any]:
    """Multiply two numbers."""
    a = args.get("a")
    b = args.get("b")

    if a is None or b is None:
        return {
            "content": [{"type": "text", "text": "Error: Both 'a' and 'b' are required"}],
            "is_error": True,
        }

    result = a * b
    return {
        "content": [{"type": "text", "text": f"{a} * {b} = {result}"}],
    }


@tool(
    name="divide",
    description="Divide one number by another. Returns a divided by b.",
    input_schema={
        "type": "object",
        "properties": {
            "a": {"type": "number", "description": "Numerator (number to be divided)"},
            "b": {"type": "number", "description": "Denominator (number to divide by)"},
        },
        "required": ["a", "b"],
    },
)
async def divide(args: dict[str, Any]) -> dict[str, Any]:
    """Divide two numbers."""
    a = args.get("a")
    b = args.get("b")

    if a is None or b is None:
        return {
            "content": [{"type": "text", "text": "Error: Both 'a' and 'b' are required"}],
            "is_error": True,
        }

    if b == 0:
        return {
            "content": [{"type": "text", "text": "Error: Cannot divide by zero"}],
            "is_error": True,
        }

    result = a / b
    return {
        "content": [{"type": "text", "text": f"{a} / {b} = {result}"}],
    }
