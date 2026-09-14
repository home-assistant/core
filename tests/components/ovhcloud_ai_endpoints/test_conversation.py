"""Tests for the OVHcloud AI Endpoints conversation entity."""

import datetime
from unittest.mock import AsyncMock

from freezegun import freeze_time
from openai import OpenAIError
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
from homeassistant.components.ovhcloud_ai_endpoints.entity import (
    _convert_content_to_chat_message,
    _decode_tool_arguments,
)
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
    """Test entity registry snapshot for conversation entities."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_default_prompt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_openai_client: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Test that the default prompt works."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)
    result = await conversation.async_converse(
        hass,
        "hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.meta_llama_3_3_70b_instruct",
    )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_chat_log.content[1:] == snapshot
    call = mock_openai_client.chat.completions.create.call_args_list[0][1]
    assert call["model"] == "Meta-Llama-3_3-70B-Instruct"
    assert "extra_headers" not in call
    assert "extra_body" not in call
    assert "user" not in call


async def test_thinking_tags_extracted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """``<think>…</think>`` markup must be extracted into thinking_content."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=ChatCompletion(
            id="chatcmpl-thinking",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="<think>Let me think.</think>\n\nThe answer is 42.",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="Qwen3-32B",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        )
    )

    result = await conversation.async_converse(
        hass,
        "What is the answer?",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.meta_llama_3_3_70b_instruct",
    )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assistant = mock_chat_log.content[-1]
    assert isinstance(assistant, conversation.AssistantContent)
    assert assistant.content == "The answer is 42."
    assert assistant.thinking_content == "Let me think."


async def test_thinking_only_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """A response containing only ``<think>…</think>`` should leave content as None."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=ChatCompletion(
            id="chatcmpl-think-only",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="<think>Reasoning…</think>",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="Qwen3-32B",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=5, prompt_tokens=8, total_tokens=13
            ),
        )
    )

    await conversation.async_converse(
        hass,
        "hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.meta_llama_3_3_70b_instruct",
    )

    assistant = mock_chat_log.content[-1]
    assert isinstance(assistant, conversation.AssistantContent)
    assert assistant.content is None
    assert assistant.thinking_content == "Reasoning…"


def _completion_with_extras(content: str | None, **extras: str) -> ChatCompletion:
    """Build a ChatCompletion whose message carries extra (vLLM) fields."""
    return ChatCompletion(
        id="chatcmpl-extras",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(
                    content=content,
                    role="assistant",
                    function_call=None,
                    tool_calls=None,
                    **extras,
                ),
            )
        ],
        created=1700000000,
        model="Qwen3-32B",
        object="chat.completion",
        system_fingerprint=None,
        usage=CompletionUsage(completion_tokens=9, prompt_tokens=8, total_tokens=17),
    )


async def test_reasoning_field_extracted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Reasoning text in ``message.reasoning`` must populate thinking_content."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_completion_with_extras(
            "The answer is 42.", reasoning="Hidden chain of thought"
        )
    )

    await conversation.async_converse(
        hass,
        "What is the answer?",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.meta_llama_3_3_70b_instruct",
    )

    assistant = mock_chat_log.content[-1]
    assert isinstance(assistant, conversation.AssistantContent)
    assert assistant.content == "The answer is 42."
    assert assistant.thinking_content == "Hidden chain of thought"


async def test_reasoning_content_field_extracted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Reasoning text in ``message.reasoning_content`` must populate thinking_content."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_completion_with_extras(
            "Final answer.", reasoning_content="DeepSeek-style reasoning"
        )
    )

    await conversation.async_converse(
        hass,
        "Question",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.meta_llama_3_3_70b_instruct",
    )

    assistant = mock_chat_log.content[-1]
    assert isinstance(assistant, conversation.AssistantContent)
    assert assistant.content == "Final answer."
    assert assistant.thinking_content == "DeepSeek-style reasoning"


async def test_reasoning_priority_over_think_tags(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """``message.reasoning`` wins over inline ``<think>`` markup in content."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_completion_with_extras(
            "<think>from tag</think>actual", reasoning="from field"
        )
    )

    await conversation.async_converse(
        hass,
        "Question",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.meta_llama_3_3_70b_instruct",
    )

    assistant = mock_chat_log.content[-1]
    assert isinstance(assistant, conversation.AssistantContent)
    assert assistant.thinking_content == "from field"
    # When the reasoning field is present, content is kept as-is — we trust
    # the server to have placed the user-facing answer in `content` already.
    assert assistant.content == "<think>from tag</think>actual"


async def test_empty_api_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """An empty choices response should yield an error conversation result."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[],
            created=1700000000,
            model="Meta-Llama-3_3-70B-Instruct",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(completion_tokens=0, prompt_tokens=8, total_tokens=8),
        )
    )

    result = await conversation.async_converse(
        hass,
        "hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.meta_llama_3_3_70b_instruct",
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR


@pytest.mark.parametrize("enable_assist", [True])
async def test_function_call(
    hass: HomeAssistant,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_openai_client: AsyncMock,
) -> None:
    """Test tool calling end-to-end with the conversation entity."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    mock_chat_log.async_add_user_content(
        conversation.UserContent(content="What time is it?")
    )
    mock_chat_log.async_add_assistant_content_without_tools(
        conversation.AssistantContent(
            agent_id="conversation.meta_llama_3_3_70b_instruct",
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
            agent_id="conversation.meta_llama_3_3_70b_instruct",
            tool_call_id="mock_tool_call_id",
            tool_name="HassGetCurrentTime",
            tool_result={
                "speech": {"plain": {"speech": "12:00 PM", "extra_data": None}},
                "response_type": "action_done",
                "speech_slots": {"time": datetime.time(12, 0)},
                "data": {"success": [], "failed": []},
            },
        )
    )
    mock_chat_log.async_add_assistant_content_without_tools(
        conversation.AssistantContent(
            agent_id="conversation.meta_llama_3_3_70b_instruct",
            content="12:00 PM",
        )
    )

    mock_chat_log.mock_tool_results(
        {
            "call_call_1": "value1",
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
            model="Meta-Llama-3_3-70B-Instruct",
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
            model="Meta-Llama-3_3-70B-Instruct",
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
        agent_id="conversation.meta_llama_3_3_70b_instruct",
    )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_chat_log.content[1:] == snapshot
    assert mock_openai_client.chat.completions.create.call_count == 2


async def test_openai_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """An OpenAIError from the SDK should surface an error conversation result."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    mock_openai_client.chat.completions.create.side_effect = OpenAIError("boom")

    result = await conversation.async_converse(
        hass,
        "hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.meta_llama_3_3_70b_instruct",
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR


async def test_supported_languages(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """The conversation entity must advertise universal language support."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    agent = conversation.async_get_agent(
        hass, "conversation.meta_llama_3_3_70b_instruct"
    )
    assert agent is not None
    assert agent.supported_languages == MATCH_ALL


async def test_converse_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """A ConverseError from chat_log.async_provide_llm_data surfaces as ERROR."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)

    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_LLM_HASS_API: "invalid_llm_api"},
    )
    await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass,
        "hello",
        None,
        Context(),
        agent_id="conversation.meta_llama_3_3_70b_instruct",
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR


def test_decode_tool_arguments_invalid_json() -> None:
    """Malformed tool-call JSON arguments raise HomeAssistantError."""
    with pytest.raises(HomeAssistantError, match="Unexpected tool argument response"):
        _decode_tool_arguments("{not-json")


def test_convert_content_unmapped() -> None:
    """Content that cannot be mapped to a Completions message returns None."""
    assert (
        _convert_content_to_chat_message(conversation.SystemContent(content="")) is None
    )
