"""Tests for the OpenRouter integration."""

import datetime
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
from openai.types import CompletionUsage
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message_function_tool_call_param import Function
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.const import Platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er, intent
from homeassistant.helpers.llm import ToolInput

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.conversation import MockChatLog, mock_chat_log  # noqa: F401


@pytest.fixture(autouse=True)
def freeze_the_time():
    """Freeze the time."""
    with freeze_time("2024-05-24 12:00:00", tz_offset=0):
        yield


@pytest.mark.parametrize("enable_assist", [True, False], ids=["assist", "no_assist"])
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
        [Platform.CONVERSATION],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


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
    assert call["model"] == "openai/gpt-3.5-turbo"
    assert call["extra_headers"] == {
        "HTTP-Referer": "https://www.home-assistant.io/integrations/open_router",
        "X-Title": "Home Assistant",
    }


@pytest.mark.parametrize("enable_assist", [True])
async def test_reasoning_details_preserved(
    hass: HomeAssistant,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test that reasoning_details from the model response are preserved in subsequent API calls.

    OpenRouter requires reasoning_details to be passed back to the API when using
    reasoning models (e.g. DeepSeek R1, Gemini thinking, Anthropic extended thinking)
    so the model can continue its reasoning chain across tool-call turns.
    """
    await setup_integration(hass, mock_config_entry)

    reasoning_details = [
        {
            "type": "reasoning.text",
            "text": "Let me think through this step by step...",
            "id": "reasoning-text-1",
            "format": "anthropic-claude-v1",
            "index": 0,
        }
    ]

    # First response: assistant uses a tool and includes reasoning_details
    first_message = ChatCompletionMessage(
        content=None,
        role="assistant",
        function_call=None,
        tool_calls=[
            ChatCompletionMessageFunctionToolCall(
                id="call_reasoning_1",
                function=Function(
                    arguments='{"param1":"value1"}',
                    name="test_tool",
                ),
                type="function",
            )
        ],
        reasoning_details=reasoning_details,
    )

    mock_chat_log.mock_tool_results({"call_reasoning_1": "tool_result_value"})

    mock_openai_client.chat.completions.create.side_effect = (
        ChatCompletion(
            id="chatcmpl-reasoning-turn-1",
            choices=[
                Choice(
                    finish_reason="tool_calls",
                    index=0,
                    message=first_message,
                )
            ],
            created=1700000000,
            model="deepseek/deepseek-r1",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=50, prompt_tokens=20, total_tokens=70
            ),
        ),
        ChatCompletion(
            id="chatcmpl-reasoning-turn-2",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="I have completed the task using my reasoning.",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="deepseek/deepseek-r1",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=15, prompt_tokens=30, total_tokens=45
            ),
        ),
    )

    result = await conversation.async_converse(
        hass,
        "Please use your reasoning to help me.",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.gpt_3_5_turbo",
    )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_openai_client.chat.completions.create.call_count == 2

    # Verify reasoning_details are included in the second API call's messages
    second_call_messages = mock_openai_client.chat.completions.create.call_args_list[1][
        1
    ]["messages"]
    assistant_messages = [
        m for m in second_call_messages if m.get("role") == "assistant"
    ]
    assert len(assistant_messages) >= 1, "Expected at least one assistant message"
    assert "reasoning_details" in assistant_messages[0], (
        "reasoning_details must be preserved in assistant message for next turn"
    )
    assert assistant_messages[0]["reasoning_details"] == reasoning_details


@pytest.mark.parametrize("enable_assist", [True])
async def test_reasoning_details_not_present(
    hass: HomeAssistant,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test that messages without reasoning_details are handled gracefully (backward compat)."""
    await setup_integration(hass, mock_config_entry)

    # First response: tool call but NO reasoning_details (standard model)
    mock_chat_log.mock_tool_results({"call_no_reasoning": "some_result"})

    mock_openai_client.chat.completions.create.side_effect = (
        ChatCompletion(
            id="chatcmpl-no-reasoning-1",
            choices=[
                Choice(
                    finish_reason="tool_calls",
                    index=0,
                    message=ChatCompletionMessage(
                        content=None,
                        role="assistant",
                        function_call=None,
                        tool_calls=[
                            ChatCompletionMessageFunctionToolCall(
                                id="call_no_reasoning",
                                function=Function(
                                    arguments='{"param1":"value1"}',
                                    name="test_tool",
                                ),
                                type="function",
                            )
                        ],
                    ),
                )
            ],
            created=1700000000,
            model="openai/gpt-4o",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        ),
        ChatCompletion(
            id="chatcmpl-no-reasoning-2",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="Done without reasoning.",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="openai/gpt-4o",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        ),
    )

    result = await conversation.async_converse(
        hass,
        "Please do the task.",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.gpt_3_5_turbo",
    )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_openai_client.chat.completions.create.call_count == 2

    # Verify no reasoning_details key is injected when the model didn't return any
    second_call_messages = mock_openai_client.chat.completions.create.call_args_list[1][
        1
    ]["messages"]
    assistant_messages = [
        m for m in second_call_messages if m.get("role") == "assistant"
    ]
    assert len(assistant_messages) >= 1
    assert "reasoning_details" not in assistant_messages[0], (
        "reasoning_details should not be injected when the model did not return any"
    )


@pytest.mark.parametrize("enable_assist", [True])
async def test_function_call(
    hass: HomeAssistant,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_openai_client: AsyncMock,
) -> None:
    """Test function call from the assistant."""
    await setup_integration(hass, mock_config_entry)

    # Add some pre-existing content from conversation.default_agent
    mock_chat_log.async_add_user_content(
        conversation.UserContent(content="What time is it?")
    )
    mock_chat_log.async_add_assistant_content_without_tools(
        conversation.AssistantContent(
            agent_id="conversation.gpt_3_5_turbo",
            tool_calls=[
                ToolInput(
                    tool_name="HassGetCurrentTime",
                    tool_args={},
                    id="mock_tool_call_id",
                    external=True,
                )
            ],
        )
    )
    mock_chat_log.async_add_assistant_content_without_tools(
        conversation.ToolResultContent(
            agent_id="conversation.gpt_3_5_turbo",
            tool_call_id="mock_tool_call_id",
            tool_name="HassGetCurrentTime",
            tool_result={
                "speech": {"plain": {"speech": "12:00 PM", "extra_data": None}},
                "response_type": "action_done",
                "speech_slots": {"time": datetime.time(12, 0)},
                "data": {"targets": [], "success": [], "failed": []},
            },
        )
    )
    mock_chat_log.async_add_assistant_content_without_tools(
        conversation.AssistantContent(
            agent_id="conversation.gpt_3_5_turbo",
            content="12:00 PM",
        )
    )

    mock_chat_log.mock_tool_results(
        {
            "call_call_1": "value1",
            "call_call_2": "value2",
        }
    )

    mock_openai_client.chat.completions.create.side_effect = (
        ChatCompletion(
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
                            ChatCompletionMessageFunctionToolCall(
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
        ),
        ChatCompletion(
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
        ),
    )

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
    assert mock_openai_client.chat.completions.create.call_count == 2
    assert (
        mock_openai_client.chat.completions.create.call_args.kwargs["messages"]
        == snapshot
    )
