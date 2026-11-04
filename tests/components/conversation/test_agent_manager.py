"""Test agent manager."""

from unittest.mock import patch

from homeassistant.components.conversation import (
    ConversationInput,
    ConversationResult,
    async_converse,
    async_get_chat_log,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import chat_session
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


async def test_async_converse_error_in_open_turn(
    hass: HomeAssistant,
    init_components: None,
    mock_conversation_input: ConversationInput,
) -> None:
    """Test an error of the agent is added to the open turn of the caller."""
    with (
        chat_session.async_get_chat_session(hass, "koala", context=None) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
        patch(
            "homeassistant.components.conversation.default_agent.DefaultAgent._async_handle_message",
            side_effect=HomeAssistantError("Provider is down"),
        ),
    ):
        await async_converse(hass, "Hello", "koala", Context())

    assert [(c.role, c.content) for c in chat_log.content[1:]] == [
        ("user", "Hello"),
        ("assistant", "Error: Provider is down"),
    ]
