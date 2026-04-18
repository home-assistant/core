"""Tests for the OpenAI Conversation entity."""

import voluptuous as vol

from homeassistant.components.openai_conversation.entity import (
    _format_structured_output,
)
from homeassistant.helpers import selector


async def test_format_structured_output() -> None:
    """Test the format_structured_output function."""
    schema = vol.Schema(
        {
            vol.Required("name"): selector.TextSelector(),
            vol.Optional("age"): selector.NumberSelector(
                config=selector.NumberSelectorConfig(
                    min=0,
                    max=120,
                ),
            ),
            vol.Required("stuff"): selector.ObjectSelector(
                {
                    "multiple": True,
                    "fields": {
                        "item_name": {
                            "selector": {"text": None},
                        },
                        "item_value": {
                            "selector": {"text": None},
                        },
                    },
                }
            ),
        }
    )
    assert _format_structured_output(schema, None) == {
        "additionalProperties": False,
        "properties": {
            "age": {
                "maximum": 120.0,
                "minimum": 0.0,
                "type": [
                    "number",
                    "null",
                ],
            },
            "name": {
                "type": "string",
            },
            "stuff": {
                "items": {
                    "properties": {
                        "item_name": {
                            "type": ["string", "null"],
                        },
                        "item_value": {
                            "type": ["string", "null"],
                        },
                    },
                    "required": [
                        "item_name",
                        "item_value",
                    ],
                    "type": "object",
                    "additionalProperties": False,
                    "strict": True,
                },
                "type": "array",
            },
        },
        "required": [
            "name",
            "stuff",
            "age",
        ],
        "strict": True,
        "type": "object",
    }
