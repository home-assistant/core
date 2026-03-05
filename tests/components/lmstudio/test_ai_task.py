"""Test AI Task platform of LM Studio integration."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components import ai_task
from homeassistant.components.lmstudio.client import LMStudioStreamEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


async def _stream_chat(
    self, payload: dict[str, Any]
) -> AsyncGenerator[LMStudioStreamEvent]:
    """Mock streaming response for AI task."""
    yield LMStudioStreamEvent("message.start", {})
    yield LMStudioStreamEvent("message.delta", {"content": "Generated "})
    yield LMStudioStreamEvent("message.delta", {"content": "data"})
    yield LMStudioStreamEvent("message.end", {})
    yield LMStudioStreamEvent("chat.end", {"response_id": "resp-1"})


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test AI Task data generation."""
    entity_id = "ai_task.lm_studio_ai_task"

    with patch(
        "homeassistant.components.lmstudio.client.LMStudioClient.async_stream_chat",
        new=_stream_chat,
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Generate test data",
        )

    assert result.data == "Generated data"


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test AI Task structured data generation."""
    entity_id = "ai_task.lm_studio_ai_task"

    async def stream_chat(
        self, payload: dict[str, Any]
    ) -> AsyncGenerator[LMStudioStreamEvent]:
        yield LMStudioStreamEvent("message.start", {})
        yield LMStudioStreamEvent("message.delta", {"content": '{"answer": "ok"}'})
        yield LMStudioStreamEvent("message.end", {})
        yield LMStudioStreamEvent("chat.end", {"response_id": "resp-1"})

    with patch(
        "homeassistant.components.lmstudio.client.LMStudioClient.async_stream_chat",
        new=stream_chat,
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Generate structured data",
            structure=vol.Schema({vol.Required("answer"): str}),
        )

    assert result.data == {"answer": "ok"}


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_structured_data_invalid_json(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test AI Task raises error when model returns invalid JSON for structured data."""
    entity_id = "ai_task.lm_studio_ai_task"

    async def stream_chat(
        self, payload: dict[str, Any]
    ) -> AsyncGenerator[LMStudioStreamEvent]:
        yield LMStudioStreamEvent("message.start", {})
        yield LMStudioStreamEvent("message.delta", {"content": "not valid json {"})
        yield LMStudioStreamEvent("message.end", {})
        yield LMStudioStreamEvent("chat.end", {"response_id": "resp-1"})

    with (
        patch(
            "homeassistant.components.lmstudio.client.LMStudioClient.async_stream_chat",
            new=stream_chat,
        ),
        pytest.raises(HomeAssistantError) as err,
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Generate structured data",
            structure=vol.Schema({vol.Required("answer"): str}),
        )

    assert err.value.translation_key == "invalid_structured_response"


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data_no_assistant_content(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test AI Task raises error when model returns no assistant content."""
    entity_id = "ai_task.lm_studio_ai_task"

    async def stream_chat(
        self, payload: dict[str, Any]
    ) -> AsyncGenerator[LMStudioStreamEvent]:
        # Yields nothing — chat log ends without AssistantContent
        yield LMStudioStreamEvent("chat.end", {"response_id": "resp-1"})

    with (
        patch(
            "homeassistant.components.lmstudio.client.LMStudioClient.async_stream_chat",
            new=stream_chat,
        ),
        pytest.raises(HomeAssistantError) as err,
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Generate data",
        )

    assert err.value.translation_key == "no_assistant_response"
