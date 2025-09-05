"""Test AI Task structured data generation."""

from unittest.mock import AsyncMock, patch

from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import ai_task
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.open_router.PLATFORMS",
        [Platform.AI_TASK],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_generate_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task data generation."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "ai_task.gemini_1_5_pro"

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="The test data",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="x-ai/grok-3",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        )
    )

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=entity_id,
        instructions="Generate test data",
    )

    assert result.data == "The test data"


async def test_generate_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task structured data generation."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content='{"characters": ["Mario", "Luigi"]}',
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="x-ai/grok-3",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        )
    )

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id="ai_task.gemini_1_5_pro",
        instructions="Generate test data",
        structure=vol.Schema(
            {
                vol.Required("characters"): selector.selector(
                    {
                        "text": {
                            "multiple": True,
                        }
                    }
                )
            },
        ),
    )

    assert result.data == {"characters": ["Mario", "Luigi"]}
    assert mock_openai_client.chat.completions.create.call_args_list[0][1][
        "response_format"
    ] == {
        "json_schema": {
            "name": "Test Task",
            "schema": {
                "properties": {
                    "characters": {
                        "items": {"type": "string"},
                        "type": "array",
                    }
                },
                "required": ["characters"],
                "type": "object",
            },
            "strict": True,
        },
        "type": "json_schema",
    }


async def test_generate_invalid_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task with invalid JSON response."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="INVALID JSON RESPONSE",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="x-ai/grok-3",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        )
    )

    with pytest.raises(
        HomeAssistantError, match="Error with OpenRouter structured response"
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_1_5_pro",
            instructions="Generate test data",
            structure=vol.Schema(
                {
                    vol.Required("characters"): selector.selector(
                        {
                            "text": {
                                "multiple": True,
                            }
                        }
                    )
                },
            ),
        )
