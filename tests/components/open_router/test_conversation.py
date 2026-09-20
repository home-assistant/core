"""Tests for the OpenRouter integration."""

from collections.abc import AsyncGenerator
import datetime
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import (
    Choice as ChunkChoice,
    ChoiceDelta,
    ChoiceDeltaToolCall,
    ChoiceDeltaToolCallFunction,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.const import Platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er, intent
from homeassistant.helpers.llm import ToolInput, ToolResult

from . import setup_integration
from .conftest import get_generator_from_data

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

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert mock_chat_log.content[1:] == snapshot
    call = mock_openai_client.chat.completions.create.call_args_list[0][1]
    assert call["model"] == "openai/gpt-3.5-turbo"
    assert call["extra_headers"] == {
        "HTTP-Referer": "https://www.home-assistant.io/integrations/open_router",
        "X-Title": "Home Assistant",
    }


@pytest.mark.parametrize(
    ("web_search", "expected_server_tools", "expected_model_suffix"),
    [
        ("plugin", None, ":online"),
        (
            "tool",
            [{"type": "openrouter:web_search", "parameters": {"engine": "auto"}}],
            "",
        ),
        ("off", None, ""),
    ],
    ids=["web_search_plugin_enabled", "web_search_enabled", "web_search_disabled"],
)
async def test_web_search(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
    web_search: str,
    expected_server_tools: dict[str, str] | None,
    expected_model_suffix: str,
) -> None:
    """Test that web search works correctly."""
    await setup_integration(hass, mock_config_entry)
    await conversation.async_converse(
        hass,
        "hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.gpt_3_5_turbo",
    )
    call = mock_openai_client.chat.completions.create.call_args_list[0][1]
    expected_model = "openai/gpt-3.5-turbo" + expected_model_suffix
    assert call["model"] == expected_model
    assert call["extra_body"].get("tools") == expected_server_tools


@pytest.mark.parametrize(
    ("web_search", "enable_assist"),
    [("tool", True)],
)
async def test_web_search_with_assist(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
    web_search: bool,
    enable_assist: bool,
) -> None:
    """Test that the web search and assist tools don't overwrite each other."""
    await setup_integration(hass, mock_config_entry)
    await conversation.async_converse(
        hass,
        "hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.gpt_3_5_turbo",
    )
    call = mock_openai_client.chat.completions.create.call_args_list[0][1]
    expected_model = "openai/gpt-3.5-turbo"
    assert call["model"] == expected_model
    assert call["extra_body"].get("tools")
    # Ensure the web search tool is in the tools list
    assert {"type": "openrouter:web_search", "parameters": {"engine": "auto"}} in call[
        "extra_body"
    ]["tools"]
    # Ensure llm__GetDateTime is in the tools list
    assert any(
        tool.get("function", {}).get("name") == "llm__GetDateTime"
        for tool in call["extra_body"]["tools"]
    )


async def test_empty_api_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Test that an empty choices response raises HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=get_generator_from_data(
            [
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
                    choices=[],
                    created=1700000000,
                    model="gpt-3.5-turbo-0613",
                    object="chat.completion.chunk",
                    system_fingerprint=None,
                    usage=CompletionUsage(
                        completion_tokens=0, prompt_tokens=8, total_tokens=8
                    ),
                )
            ]
        )
    )

    result = await conversation.async_converse(
        hass,
        "hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.gpt_3_5_turbo",
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR


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
            result=ToolResult(
                data={
                    "speech": {"plain": {"speech": "12:00 PM", "extra_data": None}},
                    "response_type": "action_done",
                    "speech_slots": {"time": datetime.time(12, 0)},
                    "data": {"success": [], "failed": []},
                }
            ),
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
        get_generator_from_data(
            [
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
                    choices=[
                        ChunkChoice.model_construct(
                            index=0,
                            finish_reason=None,
                            delta=ChoiceDelta(
                                role="assistant",
                                content=None,
                                tool_calls=[
                                    ChoiceDeltaToolCall(
                                        index=0,
                                        id="call_call_1",
                                        type="function",
                                        function=ChoiceDeltaToolCallFunction(
                                            name="test_tool",
                                            arguments='{"param1"',
                                        ),
                                    )
                                ],
                            ),
                        ),
                    ],
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    system_fingerprint=None,
                ),
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
                    choices=[
                        ChunkChoice.model_construct(
                            index=0,
                            finish_reason=None,
                            delta=ChoiceDelta(
                                content=None,
                                tool_calls=[
                                    ChoiceDeltaToolCall(
                                        index=1,
                                        id="call_call_2",
                                        type="function",
                                        function=ChoiceDeltaToolCallFunction(
                                            name="test_tool",
                                            arguments='{"param2"',
                                        ),
                                    )
                                ],
                            ),
                        ),
                    ],
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    system_fingerprint=None,
                ),
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
                    choices=[
                        ChunkChoice.model_construct(
                            index=0,
                            finish_reason=None,
                            delta=ChoiceDelta(
                                content=None,
                                tool_calls=[
                                    ChoiceDeltaToolCall(
                                        index=0,
                                        function=ChoiceDeltaToolCallFunction(
                                            arguments=':"call1"}'
                                        ),
                                    )
                                ],
                            ),
                        ),
                    ],
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    system_fingerprint=None,
                ),
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
                    choices=[
                        ChunkChoice.model_construct(
                            index=0,
                            finish_reason=None,
                            delta=ChoiceDelta(
                                content=None,
                                tool_calls=[
                                    ChoiceDeltaToolCall(
                                        index=1,
                                        function=ChoiceDeltaToolCallFunction(
                                            arguments=':"call2"}'
                                        ),
                                    )
                                ],
                            ),
                        ),
                    ],
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    system_fingerprint=None,
                ),
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ZYXWVUTSRQPONMLKJIH",
                    choices=[
                        ChunkChoice.model_construct(
                            index=0, finish_reason="tool_calls", delta=ChoiceDelta()
                        )
                    ],
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    system_fingerprint=None,
                ),
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ZYXWVUTSRQPONMLKJIH",
                    choices=[],
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    system_fingerprint=None,
                    usage=CompletionUsage(
                        completion_tokens=9, prompt_tokens=8, total_tokens=17
                    ),
                ),
            ]
        ),
        get_generator_from_data(
            [
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ZYXWVUTSRQPONMLKJIH",
                    choices=[
                        ChunkChoice.model_construct(
                            index=0,
                            delta=ChoiceDelta(
                                role="assistant",
                                content="I have successfully called the function",
                            ),
                            finish_reason="stop",
                        )
                    ],
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    system_fingerprint=None,
                )
            ]
        ),
    )

    result = await conversation.async_converse(
        hass,
        "Please call the test function",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.gpt_3_5_turbo",
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    # Don't test the prompt, as it's not deterministic
    assert mock_chat_log.content[1:] == snapshot
    assert mock_openai_client.chat.completions.create.call_count == 2
    assert (
        mock_openai_client.chat.completions.create.call_args.kwargs["messages"]
        == snapshot
    )


async def test_streaming_response(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Test streaming response from the assistant."""

    async def mock_stream() -> AsyncGenerator[ChatCompletionChunk]:
        yield ChatCompletionChunk.model_construct(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                ChunkChoice.model_construct(
                    index=0,
                    delta=ChoiceDelta(role="assistant", content="Hello"),
                    finish_reason=None,
                )
            ],
            created=1700000000,
            model="gpt-3.5-turbo",
            object="chat.completion.chunk",
        )

        yield ChatCompletionChunk.model_construct(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                ChunkChoice.model_construct(
                    index=0, delta=ChoiceDelta(content=" World!"), finish_reason=None
                )
            ],
            created=1700000000,
            model="gpt-3.5-turbo",
            object="chat.completion.chunk",
        )

        yield ChatCompletionChunk.model_construct(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[ChunkChoice(index=0, delta=ChoiceDelta(), finish_reason="stop")],
            created=1700000000,
            model="gpt-3.5-turbo",
            object="chat.completion.chunk",
        )

    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create.return_value = mock_stream()

    result = await conversation.async_converse(
        hass,
        "Please stream a response",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.gpt_3_5_turbo",
    )

    assert mock_openai_client.chat.completions.create.call_args.kwargs["stream"] is True

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "Hello World!"

    content = mock_chat_log.content[1:]
    assert len(content) == 2
    assert content[0].role == "user"
    assert content[0].content == "Please stream a response"
    assert content[1].role == "assistant"
    assert content[1].content == "Hello World!"
