"""Tests for the OpenAI integration."""

from unittest.mock import AsyncMock, patch

from httpx import Response
from openai import RateLimitError
from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.completion_usage import CompletionUsage
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, intent

from tests.common import MockConfigEntry


@pytest.mark.parametrize("agent_id", [None, "conversation.openai"])
async def test_default_prompt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    agent_id: str,
) -> None:
    """Test that the default prompt works."""
    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)
    for i in range(3):
        area_registry.async_create(f"{i}Empty Area")

    if agent_id is None:
        agent_id = mock_config_entry.entry_id

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "1234")},
        name="Test Device",
        manufacturer="Test Manufacturer",
        model="Test Model",
        suggested_area="Test Area",
    )
    for i in range(3):
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={("test", f"{i}abcd")},
            name="Test Service",
            manufacturer="Test Manufacturer",
            model="Test Model",
            suggested_area="Test Area",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "5678")},
        name="Test Device 2",
        manufacturer="Test Manufacturer 2",
        model="Device 2",
        suggested_area="Test Area 2",
    )
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "9876")},
        name="Test Device 3",
        manufacturer="Test Manufacturer 3",
        model="Test Model 3A",
        suggested_area="Test Area 2",
    )
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "qwer")},
        name="Test Device 4",
        suggested_area="Test Area 2",
    )
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "9876-disabled")},
        name="Test Device 3",
        manufacturer="Test Manufacturer 3",
        model="Test Model 3A",
        suggested_area="Test Area 2",
    )
    device_registry.async_update_device(
        device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "9876-no-name")},
        manufacturer="Test Manufacturer NoName",
        model="Test Model NoName",
        suggested_area="Test Area 2",
    )
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "9876-integer-values")},
        name=1,
        manufacturer=2,
        model=3,
        suggested_area="Test Area 2",
    )
    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="Hello, how can I help you?",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="gpt-3.5-turbo-0613",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        ),
    ) as mock_create:
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=agent_id
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_create.mock_calls[0][2]["messages"] == snapshot


async def test_error_handling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test that the default prompt works."""
    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        side_effect=RateLimitError(
            response=Response(status_code=None, request=""), body=None, message=None
        ),
    ):
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result


async def test_template_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that template error handling works."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            "prompt": "talk like a {% if True %}smarthome{% else %}pirate please.",
        },
    )
    with (
        patch(
            "openai.resources.models.AsyncModels.list",
        ),
        patch(
            "openai.resources.chat.completions.AsyncCompletions.create",
            new_callable=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result


async def test_conversation_agent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test OpenAIAgent."""
    agent = conversation.get_agent_manager(hass).async_get_agent(
        mock_config_entry.entry_id
    )
    assert agent.supported_languages == "*"
