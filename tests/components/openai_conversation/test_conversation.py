"""Tests for the OpenAI integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from httpx import Response
from openai import RateLimitError
from openai.types.chat.chat_completion_chunk import (
    ChatCompletionChunk,
    Choice,
    ChoiceDelta,
    ChoiceDeltaToolCall,
    ChoiceDeltaToolCallFunction,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.conversation import (
    MockChatLog,
    mock_chat_log,  # noqa: F401
)

ASSIST_RESPONSE_FINISH = (
    # Assistant message
    ChatCompletionChunk(
        id="chatcmpl-B",
        created=1700000000,
        model="gpt-4-1106-preview",
        object="chat.completion.chunk",
        choices=[Choice(index=0, delta=ChoiceDelta(content="Cool"))],
    ),
    # Finish stream
    ChatCompletionChunk(
        id="chatcmpl-B",
        created=1700000000,
        model="gpt-4-1106-preview",
        object="chat.completion.chunk",
        choices=[Choice(index=0, finish_reason="stop", delta=ChoiceDelta())],
    ),
)


@pytest.fixture
def mock_create_stream() -> Generator[AsyncMock]:
    """Mock stream response."""

    async def mock_generator(stream):
        for value in stream:
            yield value

    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        AsyncMock(),
    ) as mock_create:
        mock_create.side_effect = lambda **kwargs: mock_generator(
            mock_create.return_value.pop(0)
        )

        yield mock_create


async def test_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test entity properties."""
    state = hass.states.get("conversation.openai")
    assert state
    assert state.attributes["supported_features"] == 0

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_LLM_HASS_API: "assist",
        },
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    state = hass.states.get("conversation.openai")
    assert state
    assert (
        state.attributes["supported_features"]
        == conversation.ConversationEntityFeature.CONTROL
    )


async def test_error_handling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test that we handle errors when calling completion API."""
    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        side_effect=RateLimitError(
            response=Response(status_code=None, request=""), body=None, message=None
        ),
    ):
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result


async def test_conversation_agent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test OpenAIAgent."""
    agent = conversation.get_agent_manager(hass).async_get_agent(
        mock_config_entry.entry_id
    )
    assert agent.supported_languages == "*"


async def test_function_call(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
    snapshot: SnapshotAssertion,
) -> None:
    """Test function call from the assistant."""
    mock_create_stream.return_value = [
        # Initial conversation
        (
            # First tool call
            ChatCompletionChunk(
                id="chatcmpl-A",
                created=1700000000,
                model="gpt-4-1106-preview",
                object="chat.completion.chunk",
                choices=[
                    Choice(
                        index=0,
                        delta=ChoiceDelta(
                            tool_calls=[
                                ChoiceDeltaToolCall(
                                    id="call_call_1",
                                    index=0,
                                    function=ChoiceDeltaToolCallFunction(
                                        name="test_tool",
                                        arguments=None,
                                    ),
                                )
                            ]
                        ),
                    )
                ],
            ),
            ChatCompletionChunk(
                id="chatcmpl-A",
                created=1700000000,
                model="gpt-4-1106-preview",
                object="chat.completion.chunk",
                choices=[
                    Choice(
                        index=0,
                        delta=ChoiceDelta(
                            tool_calls=[
                                ChoiceDeltaToolCall(
                                    index=0,
                                    function=ChoiceDeltaToolCallFunction(
                                        name=None,
                                        arguments='{"para',
                                    ),
                                )
                            ]
                        ),
                    )
                ],
            ),
            ChatCompletionChunk(
                id="chatcmpl-A",
                created=1700000000,
                model="gpt-4-1106-preview",
                object="chat.completion.chunk",
                choices=[
                    Choice(
                        index=0,
                        delta=ChoiceDelta(
                            tool_calls=[
                                ChoiceDeltaToolCall(
                                    index=0,
                                    function=ChoiceDeltaToolCallFunction(
                                        name=None,
                                        arguments='m1":"call1"}',
                                    ),
                                )
                            ]
                        ),
                    )
                ],
            ),
            # Second tool call
            ChatCompletionChunk(
                id="chatcmpl-A",
                created=1700000000,
                model="gpt-4-1106-preview",
                object="chat.completion.chunk",
                choices=[
                    Choice(
                        index=0,
                        delta=ChoiceDelta(
                            tool_calls=[
                                ChoiceDeltaToolCall(
                                    id="call_call_2",
                                    index=1,
                                    function=ChoiceDeltaToolCallFunction(
                                        name="test_tool",
                                        arguments='{"param1":"call2"}',
                                    ),
                                )
                            ]
                        ),
                    )
                ],
            ),
            # Finish stream
            ChatCompletionChunk(
                id="chatcmpl-A",
                created=1700000000,
                model="gpt-4-1106-preview",
                object="chat.completion.chunk",
                choices=[
                    Choice(index=0, finish_reason="tool_calls", delta=ChoiceDelta())
                ],
            ),
        ),
        # Response after tool responses
        ASSIST_RESPONSE_FINISH,
    ]
    mock_chat_log.mock_tool_results(
        {
            "call_call_1": "value1",
            "call_call_2": "value2",
        }
    )

    result = await conversation.async_converse(
        hass,
        "Please call the test function",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.openai",
    )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    # Don't test the prompt, as it's not deterministic
    assert mock_chat_log.content[1:] == snapshot


@pytest.mark.parametrize(
    ("description", "messages"),
    [
        (
            "Test function call started with missing arguments",
            (
                ChatCompletionChunk(
                    id="chatcmpl-A",
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    choices=[
                        Choice(
                            index=0,
                            delta=ChoiceDelta(
                                tool_calls=[
                                    ChoiceDeltaToolCall(
                                        id="call_call_1",
                                        index=0,
                                        function=ChoiceDeltaToolCallFunction(
                                            name="test_tool",
                                            arguments=None,
                                        ),
                                    )
                                ]
                            ),
                        )
                    ],
                ),
                ChatCompletionChunk(
                    id="chatcmpl-B",
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    choices=[Choice(index=0, delta=ChoiceDelta(content="Cool"))],
                ),
            ),
        ),
        (
            "Test invalid JSON",
            (
                ChatCompletionChunk(
                    id="chatcmpl-A",
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    choices=[
                        Choice(
                            index=0,
                            delta=ChoiceDelta(
                                tool_calls=[
                                    ChoiceDeltaToolCall(
                                        id="call_call_1",
                                        index=0,
                                        function=ChoiceDeltaToolCallFunction(
                                            name="test_tool",
                                            arguments=None,
                                        ),
                                    )
                                ]
                            ),
                        )
                    ],
                ),
                ChatCompletionChunk(
                    id="chatcmpl-A",
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    choices=[
                        Choice(
                            index=0,
                            delta=ChoiceDelta(
                                tool_calls=[
                                    ChoiceDeltaToolCall(
                                        index=0,
                                        function=ChoiceDeltaToolCallFunction(
                                            name=None,
                                            arguments='{"para',
                                        ),
                                    )
                                ]
                            ),
                        )
                    ],
                ),
                ChatCompletionChunk(
                    id="chatcmpl-B",
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    choices=[
                        Choice(
                            index=0,
                            delta=ChoiceDelta(content="Cool"),
                            finish_reason="tool_calls",
                        )
                    ],
                ),
            ),
        ),
    ],
)
async def test_function_call_invalid(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
    description: str,
    messages: tuple[ChatCompletionChunk],
) -> None:
    """Test function call containing invalid data."""
    mock_create_stream.return_value = [messages]

    with pytest.raises(ValueError):
        await conversation.async_converse(
            hass,
            "Please call the test function",
            "mock-conversation-id",
            Context(),
            agent_id="conversation.openai",
        )


async def test_assist_api_tools_conversion(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream,
) -> None:
    """Test that we are able to convert actual tools from Assist API."""
    for component in (
        "calendar",
        "climate",
        "cover",
        "humidifier",
        "intent",
        "light",
        "media_player",
        "script",
        "shopping_list",
        "todo",
        "vacuum",
        "weather",
    ):
        assert await async_setup_component(hass, component, {})
        hass.states.async_set(f"{component}.test", "on")
        async_expose_entity(hass, "conversation", f"{component}.test", True)

    mock_create_stream.return_value = [ASSIST_RESPONSE_FINISH]

    await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.openai"
    )

    tools = mock_create_stream.mock_calls[0][2]["tools"]
    assert tools
