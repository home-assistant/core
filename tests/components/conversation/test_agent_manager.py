"""Test agent manager."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.conversation import ConversationResult, async_converse
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.intent import IntentResponse

from . import MockAgent


@pytest.mark.usefixtures("init_components")
async def test_async_converse(hass: HomeAssistant, mock_agent: MockAgent) -> None:
    """Test the async_converse method."""
    context = Context()
    mock_agent.async_process = AsyncMock(
        return_value=ConversationResult(response=IntentResponse(language="test lang"))
    )
    await async_converse(
        hass,
        text="test command",
        conversation_id="test id",
        context=context,
        language="test lang",
        agent_id=mock_agent.agent_id,
        device_id="test device id",
        extra_system_prompt="test extra prompt",
    )

    assert mock_agent.async_process.called
    conversation_input = mock_agent.async_process.call_args[0][0]
    assert conversation_input.text == "test command"
    assert conversation_input.conversation_id == "test id"
    assert conversation_input.context is context
    assert conversation_input.language == "test lang"
    assert conversation_input.agent_id == mock_agent.agent_id
    assert conversation_input.device_id == "test device id"
    assert conversation_input.extra_system_prompt == "test extra prompt"
