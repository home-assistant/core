"""Tests for conversation utility functions."""

from homeassistant.components import conversation
from homeassistant.core import HomeAssistant
from homeassistant.helpers import chat_session, intent, llm


async def test_async_get_result_from_chat_log(
    hass: HomeAssistant,
    mock_conversation_input: conversation.ConversationInput,
) -> None:
    """Test getting result from chat log."""
    intent_response = intent.IntentResponse(language="en")
    with (
        chat_session.async_get_chat_session(hass) as session,
        conversation.async_get_chat_log(
            hass, session, mock_conversation_input
        ) as chat_log,
    ):
        chat_log.content.extend(
            [
                conversation.ToolResultContent(
                    agent_id="mock-agent-id",
                    tool_call_id="mock-tool-call-id",
                    tool_name="mock-tool-name",
                    tool_result=llm.IntentResponseDict(intent_response),
                ),
                conversation.AssistantContent(
                    agent_id="mock-agent-id",
                    content="This is a response.",
                ),
            ]
        )
        result = conversation.async_get_result_from_chat_log(
            mock_conversation_input, chat_log
        )
    # Original intent response is returned with speech set
    assert result.response is intent_response
    assert result.response.speech["plain"]["speech"] == "This is a response."
