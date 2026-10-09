"""Test OpenRouter tool formatting."""

from unittest.mock import Mock

import probatio
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.open_router.entity import _format_tool
from homeassistant.helpers import llm


def test_format_tool(snapshot: SnapshotAssertion) -> None:
    """Tool parameters use JSON Schema nullability and retain optional fields."""
    tool = Mock(
        spec=llm.Tool,
        description="Test tool",
        parameters=probatio.Schema(
            {
                probatio.Required("value"): probatio.Any(str, None),
                probatio.Optional("count"): int,
            }
        ),
    )
    tool.name = "test"

    result = _format_tool(tool, None)

    validator = probatio.from_json_schema(result["function"]["parameters"])
    validator({"value": None})
    validator({"value": "a", "count": 1})
    with pytest.raises(probatio.Invalid):
        validator({})
    assert result == snapshot
