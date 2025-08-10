"""Test the LM Studio AI task platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components import ai_task, conversation
from homeassistant.components.conversation.chat_log import AssistantContent
from homeassistant.components.lmstudio.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_ai_task_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client_config_flow: AsyncMock,
) -> None:
    """Test AI task entity setup."""
    await init_integration(hass, mock_config_entry, mock_openai_client_config_flow)

    state = hass.states.get("ai_task.lm_studio_http_localhost_1234_v1_lm_studio_ai")
    assert state is not None
    assert state.name == "LM Studio (http://localhost:1234/v1) LM Studio AI"
    assert state.state == "unknown"


async def test_ai_task_generate_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client_config_flow: AsyncMock,
) -> None:
    """Test AI task data generation."""
    await init_integration(hass, mock_config_entry, mock_openai_client_config_flow)

    # Mock the chat completion response
    mock_openai_client_config_flow.chat.completions.create.return_value = AsyncMock(
        choices=[AsyncMock(message=AsyncMock(content='{"result": "test data"}'))]
    )

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(
        "ai_task.lm_studio_http_localhost_1234_v1_lm_studio_ai"
    )
    assert entity is not None

    platform = hass.data[ai_task.DOMAIN]
    ai_task_entity = platform.get_entity(entity.entity_id)
    assert ai_task_entity is not None

    task = ai_task.GenDataTask(
        name="test_task",
        instructions="Generate some test data",
        structure=None,
    )

    chat_log = conversation.ChatLog(hass=hass, conversation_id="test_conversation_id")

    # Mock the chat log processing to add a response
    with patch.object(ai_task_entity, "_async_handle_chat_log") as mock_handle:
        mock_handle.return_value = None
        # Add the expected response to the chat log manually

        chat_log.content.append(
            AssistantContent(content='{"result": "test data"}', agent_id="test_agent")
        )

        result = await ai_task_entity._async_generate_data(task, chat_log)

    assert result.conversation_id == "test_conversation_id"
    assert result.data == '{"result": "test data"}'


async def test_ai_task_supports_streaming(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client_config_flow: AsyncMock,
) -> None:
    """Test AI task entity supports streaming."""
    await init_integration(hass, mock_config_entry, mock_openai_client_config_flow)

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(
        "ai_task.lm_studio_http_localhost_1234_v1_lm_studio_ai"
    )
    assert entity is not None

    platform = hass.data[ai_task.DOMAIN]
    ai_task_entity = platform.get_entity(entity.entity_id)
    assert ai_task_entity is not None
    assert ai_task_entity._attr_supports_streaming


async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client_config_flow: AsyncMock,
) -> None:
    """Test device info is correctly set."""
    await init_integration(hass, mock_config_entry, mock_openai_client_config_flow)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device is not None
    assert device.name == "LM Studio (http://localhost:1234/v1)"
    assert device.manufacturer == "LM Studio"
    assert device.model == "Local LLM Server"


async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Set up the LM Studio integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.lmstudio.openai.AsyncOpenAI") as mock_client:
        mock_client.return_value = mock_openai_client
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
