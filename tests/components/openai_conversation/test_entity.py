"""Tests for the OpenAI Conversation entity."""

from typing import Any

import voluptuous as vol

from homeassistant.components.openai_conversation.entity import (
    _format_structured_output,
    _format_tool,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm, selector


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


async def test_format_tool_strips_top_level_any_of() -> None:
    """Test that top-level anyOf/oneOf/allOf/enum/not are stripped from tool params.

    OpenAI requires tool parameter schemas to be of type 'object' at the top
    level with none of these keywords present. Voluptuous schemas like
    ``vol.Required(vol.Any("hours", "minutes", "seconds"))`` produce a
    top-level ``anyOf`` that must be removed.
    """

    class _TestTool(llm.Tool):
        name = "HassStartTimer"
        description = "Starts a new timer"
        parameters = vol.Schema(
            {
                vol.Required(vol.Any("hours", "minutes", "seconds")): int,
                vol.Optional("name"): str,
            }
        )

        async def async_call(
            self,
            hass: HomeAssistant,
            tool_input: llm.ToolInput,
            llm_context: llm.LLMContext,
        ) -> dict[str, Any]:
            return {}

    formatted = _format_tool(_TestTool(), None)

    assert formatted["name"] == "HassStartTimer"
    parameters = formatted["parameters"]
    assert parameters["type"] == "object"
    for key in ("oneOf", "anyOf", "allOf", "enum", "not"):
        assert key not in parameters
