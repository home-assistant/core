"""Tests for the llama.cpp conversation platform."""

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
import httpx
import openai
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessage,
    ChatCompletionMessageToolCall,
)
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_chunk import Choice as ChunkChoice, ChoiceDelta
from openai.types.chat.chat_completion_message_tool_call import Function
from openai.types.completion_usage import CompletionUsage
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.components.llama_cpp.const import CONF_STREAMING
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from .conftest import ASSIST_OPTIONS, MockChatLog

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def freeze_the_time() -> Generator[None]:
    """Freeze the time."""
    with freeze_time("2024-05-24 12:00:00", tz_offset=0):
        yield


@pytest.fixture(autouse=True)
def mock_ulid() -> Generator[AsyncMock]:
    """Mock the ulid library."""
    with patch("homeassistant.helpers.llm.ulid_now") as mock_ulid_now:
        mock_ulid_now.return_value = "mock-ulid"
        yield mock_ulid_now


@pytest.fixture(autouse=True)
async def mock_setup_integration_fixture(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Setup the integration."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_conversation_entity(
    hass: HomeAssistant,
    mock_chat_log: MockChatLog,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Verify the conversation entity is loaded."""
    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="Hello, how can I help you?",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="gpt-3.5-turbo-0613",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        ),
    ):
        result = await conversation.async_converse(
            hass,
            "hello",
            mock_chat_log.conversation_id,
            Context(),
            agent_id="conversation.llama_cpp_conversation",
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_chat_log.content[1:] == snapshot


@pytest.mark.parametrize(("config_entry_options"), [ASSIST_OPTIONS])
async def test_function_call(
    hass: HomeAssistant,
    mock_chat_log: MockChatLog,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test function call from the assistant."""
    mock_chat_log.mock_tool_results(
        {
            "call_call_1": "value1",
        }
    )

    def completion_result(
        *args: Any, messages: list[dict[str, Any]] | list[Any], **kwargs: Any
    ) -> ChatCompletion:
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

    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        side_effect=completion_result,
    ):
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            mock_chat_log.conversation_id,
            Context(),
            agent_id="conversation.llama_cpp_conversation",
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_chat_log.content[1:] == snapshot


@pytest.mark.parametrize(("config_entry_options"), [ASSIST_OPTIONS])
@pytest.mark.parametrize(
    ("tool_arguments"),
    [
        (""),
        ('{"para'),
    ],
)
async def test_function_exception(
    hass: HomeAssistant,
    mock_chat_log: MockChatLog,
    mock_config_entry: MockConfigEntry,
    tool_arguments: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test function call with exception."""

    def completion_result(
        *args: Any, messages: list[dict[str, Any]] | list[Any], **kwargs: Any
    ) -> ChatCompletion:
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
                                content="There was an error calling the function",
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
                                id="call_AbCdEfGhIjKlMnOpQrStUvWx",
                                function=Function(
                                    arguments=tool_arguments,
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

    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        side_effect=completion_result,
    ):
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            "conversation-id",
            Context(),
            agent_id="conversation.llama_cpp_conversation",
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.speech["plain"]["speech"] == snapshot


@pytest.mark.parametrize(("config_entry_options"), [ASSIST_OPTIONS])
async def test_assist_api_tools_conversion(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that we are able to convert actual tools from Assist API."""
    for component in (
        "intent",
        "todo",
        "light",
        "shopping_list",
        "humidifier",
        "climate",
        "media_player",
        "vacuum",
        "cover",
        "weather",
    ):
        assert await async_setup_component(hass, component, {})

    agent_id = mock_config_entry.entry_id
    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="Hello, how can I help you?",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="gpt-3.5-turbo-0613",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        ),
    ) as mock_create:
        await conversation.async_converse(hass, "hello", None, None, agent_id=agent_id)

    tools = mock_create.mock_calls[0][2]["tools"]
    assert tools


@pytest.mark.parametrize(("config_entry_options"), [{CONF_STREAMING: True}])
async def test_streaming_response(
    hass: HomeAssistant,
    mock_chat_log: MockChatLog,
    mock_config_entry: MockConfigEntry,
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
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        )
        yield ChatCompletionChunk.model_construct(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                ChunkChoice.model_construct(
                    index=0,
                    delta=ChoiceDelta(content=" world"),
                    finish_reason=None,
                )
            ],
            created=1700000000,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        )
        yield ChatCompletionChunk(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChoiceDelta(),
                    finish_reason="stop",
                )
            ],
            created=1700000000,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        )

    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=mock_stream(),
    ):
        result = await conversation.async_converse(
            hass,
            "hello",
            mock_chat_log.conversation_id,
            Context(),
            agent_id="conversation.llama_cpp_conversation",
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "Hello world"

    content = mock_chat_log.content[1:]
    assert len(content) == 2
    assert content[0].role == "user"
    assert content[0].content == "hello"
    assert content[1].role == "assistant"
    assert content[1].content == "Hello world"


@pytest.mark.parametrize(("config_entry_options"), [{CONF_STREAMING: True}])
async def test_streaming_response_redundant_role(
    hass: HomeAssistant,
    mock_chat_log: MockChatLog,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test streaming response where every chunk redundantly includes the role."""

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
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        )
        yield ChatCompletionChunk.model_construct(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                ChunkChoice.model_construct(
                    index=0,
                    delta=ChoiceDelta(role="assistant", content=" world"),
                    finish_reason=None,
                )
            ],
            created=1700000000,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        )
        yield ChatCompletionChunk(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChoiceDelta(role="assistant"),
                    finish_reason="stop",
                )
            ],
            created=1700000000,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        )

    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=mock_stream(),
    ):
        result = await conversation.async_converse(
            hass,
            "hello",
            mock_chat_log.conversation_id,
            Context(),
            agent_id="conversation.llama_cpp_conversation",
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "Hello world"

    content = mock_chat_log.content[1:]
    assert len(content) == 2
    assert content[0].role == "user"
    assert content[0].content == "hello"
    assert content[1].role == "assistant"
    assert content[1].content == "Hello world"


@pytest.mark.parametrize(
    ("config_entry_options"), [{CONF_LLM_HASS_API: ["non-existing"]}]
)
async def test_unknown_hass_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test when we reference an API that no longer exists."""
    result = await conversation.async_converse(
        hass, "hello", "conversation-id", Context(), agent_id=mock_config_entry.entry_id
    )

    assert result.as_dict() == snapshot


async def test_conversation_agent_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test handling of OpenAI API connection errors in conversation entity."""
    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        side_effect=openai.APIConnectionError(
            request=httpx.Request(method="POST", url="test")
        ),
    ):
        result = await conversation.async_converse(
            hass,
            "hello",
            "conversation-id",
            Context(),
            agent_id="conversation.llama_cpp_conversation",
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert (
        result.response.speech["plain"]["speech"]
        == "Cannot connect to the server: Connection error."
    )


async def test_conversation_agent_structured_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test handling of OpenAI API structured errors in conversation entity."""
    response = httpx.Response(
        status_code=402,
        request=httpx.Request(
            method="POST", url="https://api.openai.com/v1/chat/completions"
        ),
        json={
            "error": {
                "message": "Insufficient Balance",
                "type": "unknown_error",
                "param": None,
                "code": "invalid_request_error",
            }
        },
    )
    err = openai.APIStatusError(
        message="Error code: 402 - {'error': {'message': 'Insufficient Balance'}}",
        response=response,
        body=response.json(),
    )
    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        side_effect=err,
    ):
        result = await conversation.async_converse(
            hass,
            "hello",
            "conversation-id",
            Context(),
            agent_id="conversation.llama_cpp_conversation",
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert (
        result.response.speech["plain"]["speech"]
        == "Your account or API key has insufficient credits: Insufficient Balance"
    )
