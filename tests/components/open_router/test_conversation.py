"""Tests for the OpenRouter integration."""

from unittest.mock import AsyncMock

from freezegun import freeze_time
from openai.types import CompletionUsage
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionMessageToolCall,
)
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message_tool_call import Function
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.conversation import MockChatLog, mock_chat_log  # noqa: F401


@pytest.fixture(autouse=True)
def freeze_the_time():
    """Freeze the time."""
    with freeze_time("2024-05-24 12:00:00", tz_offset=0):
        yield


async def test_default_prompt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_openai_client: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Test that the default prompt works."""
    await setup_integration(hass, mock_config_entry)
    result = await conversation.async_converse(
        hass,
        "hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.gpt_3_5_turbo",
    )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_chat_log.content[1:] == snapshot
    call = mock_openai_client.chat.completions.create.call_args_list[0][1]
    assert call["model"] == "gpt-3.5-turbo"
    assert call["extra_headers"] == {
        "HTTP-Referer": "https://www.home-assistant.io/integrations/open_router",
        "X-Title": "Home Assistant",
    }


async def test_function_call(
    hass: HomeAssistant,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_openai_client: AsyncMock,
) -> None:
    """Test function call from the assistant."""
    await setup_integration(hass, mock_config_entry)

    mock_chat_log.mock_tool_results(
        {
            "call_call_1": "value1",
            "call_call_2": "value2",
        }
    )

    async def completion_result(*args, messages, **kwargs):
        for message in messages:
            role = message["role"] if isinstance(message, dict) else message.role
            if role == "tool":
                return ChatCompletion(
                    id="chatcmpl-1234567890ZYXWVUTSRQPONMLKJIH",
                    choices=[
                        Choice(
                            finish_reason="stop",
                            index=0,
                            message=ChatCompletionMessage(
                                content="I have successfully called the function",
                                role="assistant",
                                function_call=None,
                                tool_calls=None,
                            ),
                        )
                    ],
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion",
                    system_fingerprint=None,
                    usage=CompletionUsage(
                        completion_tokens=9, prompt_tokens=8, total_tokens=17
                    ),
                )

        return ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="tool_calls",
                    index=0,
                    message=ChatCompletionMessage(
                        content=None,
                        role="assistant",
                        function_call=None,
                        tool_calls=[
                            ChatCompletionMessageToolCall(
                                id="call_call_1",
                                function=Function(
                                    arguments='{"param1":"call1"}',
                                    name="test_tool",
                                ),
                                type="function",
                            )
                        ],
                    ),
                )
            ],
            created=1700000000,
            model="gpt-4-1106-preview",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        )

    mock_openai_client.chat.completions.create = completion_result

    result = await conversation.async_converse(
        hass,
        "Please call the test function",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.gpt_3_5_turbo",
    )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    # Don't test the prompt, as it's not deterministic
    assert mock_chat_log.content[1:] == snapshot
