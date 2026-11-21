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
    tool_result = llm.IntentResponseDict(intent_response)
    with (
        chat_session.async_get_chat_session(hass, context=None) as session,
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
                    result=llm.ToolResult(data=tool_result),
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
    assert tool_result["speech"] != result.response.speech


async def test_async_get_result_from_chat_log_speech_of_turn(
    hass: HomeAssistant,
    mock_conversation_input: conversation.ConversationInput,
) -> None:
    """Test the speech has all assistant text of the turn, around tool calls."""
    with (
        chat_session.async_get_chat_session(hass, context=None) as session,
        conversation.async_get_chat_log(
            hass, session, mock_conversation_input
        ) as chat_log,
    ):
        chat_log.content[1:1] = [
            conversation.UserContent(content="Previous question"),
            conversation.AssistantContent(
                agent_id="mock-agent-id", content="Previous answer."
            ),
        ]
        chat_log.llm_input_provided_index = len(chat_log.content)
        chat_log.content.extend(
            [
                conversation.AssistantContent(
                    agent_id="mock-agent-id",
                    content="I will check the status.\n",
                    tool_calls=[
                        llm.ToolInput(
                            id="mock-tool-call-id-1",
                            tool_name="mock-tool-name",
                            tool_args={},
                        )
                    ],
                ),
                conversation.ToolResultContent(
                    agent_id="mock-agent-id",
                    tool_call_id="mock-tool-call-id-1",
                    tool_name="mock-tool-name",
                    result=llm.ToolResult(data={"status": "ok"}),
                ),
                conversation.AssistantContent(
                    agent_id="mock-agent-id",
                    tool_calls=[
                        llm.ToolInput(
                            id="mock-tool-call-id-2",
                            tool_name="mock-tool-name",
                            tool_args={},
                        )
                    ],
                ),
                conversation.ToolResultContent(
                    agent_id="mock-agent-id",
                    tool_call_id="mock-tool-call-id-2",
                    tool_name="mock-tool-name",
                    result=llm.ToolResult(data={"status": "ok"}),
                ),
                conversation.AssistantContent(
                    agent_id="mock-agent-id",
                    content="The check is complete.",
                    thinking_content="Not spoken",
                ),
            ]
        )
        result = conversation.async_get_result_from_chat_log(
            mock_conversation_input, chat_log
        )

    assert (
        result.response.speech["plain"]["speech"]
        == "I will check the status.\n\nThe check is complete."
    )
