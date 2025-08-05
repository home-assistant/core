"""Test agent manager."""

from unittest.mock import patch

from homeassistant.components.conversation import ConversationResult, async_converse
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.intent import IntentResponse


async def test_async_converse(hass: HomeAssistant, init_components) -> None:
    """Test the async_converse method."""
    context = Context()
    with patch(
        "homeassistant.components.conversation.default_agent.DefaultAgent.async_process",
        return_value=ConversationResult(response=IntentResponse(language="test lang")),
    ) as mock_process:
        await async_converse(
            hass,
            text="test command",
            conversation_id="test id",
            context=context,
            language="test lang",
            agent_id="conversation.home_assistant",
            device_id="test device id",
            extra_system_prompt="test extra prompt",
        )

    assert mock_process.called
    conversation_input = mock_process.call_args[0][0]
    assert conversation_input.text == "test command"
    assert conversation_input.conversation_id == "test id"
    assert conversation_input.context is context
    assert conversation_input.language == "test lang"
    assert conversation_input.agent_id == "conversation.home_assistant"
    assert conversation_input.device_id == "test device id"
    assert conversation_input.extra_system_prompt == "test extra prompt"
