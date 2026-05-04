"""Tests for Open Responses AI tasks."""

from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components import ai_task
from homeassistant.components.open_responses.client import (
    OpenResponsesInvalidModelError,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from tests.common import MockConfigEntry


def _mock_response_stream(calls: list[dict[str, Any]], text: str) -> Any:
    """Return a streaming response mock."""

    async def stream_response(**params: Any) -> AsyncGenerator[dict[str, Any]]:
        calls.append(deepcopy(params))
        yield {
            "type": "response.output_item.added",
            "item": {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "content": [],
                "status": "in_progress",
            },
        }
        yield {"type": "response.output_text.delta", "delta": text}
        yield {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 1, "output_tokens": 1}},
        }

    return stream_response


async def test_generate_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test plain-text AI task data generation reaches the client."""
    calls: list[dict[str, Any]] = []
    mock_config_entry.runtime_data.stream_response = _mock_response_stream(
        calls, "The test data"
    )

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id="ai_task.open_responses_ai_task",
        instructions="Generate test data",
    )

    assert result.data == "The test data"
    assert calls[0]["model"] == "open-responses-model"
    assert calls[0]["input"][-1] == {
        "type": "message",
        "role": "user",
        "content": "Generate test data",
    }


async def test_generate_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test structured AI task data generation reaches the client."""
    calls: list[dict[str, Any]] = []
    mock_config_entry.runtime_data.stream_response = _mock_response_stream(
        calls, '{"characters":["Mario","Luigi"]}'
    )

    result = await ai_task.async_generate_data(
        hass,
        task_name="Character Task",
        entity_id="ai_task.open_responses_ai_task",
        instructions="Generate character data",
        structure=vol.Schema(
            {
                vol.Required("characters"): selector.selector(
                    {"text": {"multiple": True}}
                )
            }
        ),
    )

    assert result.data == {"characters": ["Mario", "Luigi"]}
    assert calls[0]["text"]["format"]["type"] == "json_schema"


async def test_generate_data_handles_invalid_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test runtime model errors are surfaced as Home Assistant errors."""

    async def stream_response(**params: Any) -> AsyncGenerator[dict[str, Any]]:
        if params["model"] == "open-responses-model":
            raise OpenResponsesInvalidModelError("missing model")
        yield {}

    mock_config_entry.runtime_data.stream_response = stream_response

    with pytest.raises(HomeAssistantError, match="Invalid Open Responses model"):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.open_responses_ai_task",
            instructions="Generate test data",
        )
