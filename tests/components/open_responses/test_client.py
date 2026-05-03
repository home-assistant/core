"""Tests for the Open Responses client."""

from pydantic import ValidationError
import pytest

from homeassistant.components.open_responses.client import _format_request_body


def test_format_request_body_preserves_tool_parameters() -> None:
    """Test request validation does not strip function tool schemas."""
    body = _format_request_body(
        {
            "model": "model",
            "input": [{"type": "message", "role": "user", "content": "hi"}],
            "stream": True,
            "tools": [
                {
                    "type": "function",
                    "name": "HassGetState",
                    "description": "Get a state",
                    "parameters": {
                        "type": "object",
                        "properties": {"entity_id": {"type": "string"}},
                        "required": ["entity_id"],
                    },
                    "strict": False,
                }
            ],
        }
    )

    assert body["tools"][0]["parameters"] == {
        "type": "object",
        "properties": {"entity_id": {"type": "string"}},
        "required": ["entity_id"],
    }


def test_format_request_body_validates_response_body() -> None:
    """Test request bodies are validated against Open Responses types."""
    with pytest.raises(ValidationError):
        _format_request_body(
            {
                "model": "model",
                "input": "ping",
                "max_output_tokens": 1,
                "stream": False,
            }
        )
