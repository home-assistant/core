"""Tests for the OpenAI integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import httpx
from openai import AuthenticationError, RateLimitError
from openai.types import ResponseFormatText
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseCreatedEvent,
    ResponseError,
    ResponseErrorEvent,
    ResponseFailedEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseFunctionToolCall,
    ResponseFunctionWebSearch,
    ResponseIncompleteEvent,
    ResponseInProgressEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseReasoningItem,
    ResponseStreamEvent,
    ResponseTextConfig,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
    ResponseWebSearchCallCompletedEvent,
    ResponseWebSearchCallInProgressEvent,
    ResponseWebSearchCallSearchingEvent,
)
from openai.types.responses.response import IncompleteDetails
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.openai_conversation.const import (
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.conversation import (
    MockChatLog,
    mock_chat_log,  # noqa: F401
)


@pytest.fixture
def mock_create_stream() -> Generator[AsyncMock]:
    """Mock stream response."""

    async def mock_generator(events, **kwargs):
        response = Response(
            id="resp_A",
            created_at=1700000000,
            error=None,
            incomplete_details=None,
            instructions=kwargs.get("instructions"),
            metadata=kwargs.get("metadata", {}),
            model=kwargs.get("model", "gpt-4o-mini"),
            object="response",
            output=[],
            parallel_tool_calls=kwargs.get("parallel_tool_calls", True),
            temperature=kwargs.get("temperature", 1.0),
            tool_choice=kwargs.get("tool_choice", "auto"),
            tools=kwargs.get("tools"),
            top_p=kwargs.get("top_p", 1.0),
            max_output_tokens=kwargs.get("max_output_tokens", 100000),
            previous_response_id=kwargs.get("previous_response_id"),
            reasoning=kwargs.get("reasoning"),
            status="in_progress",
            text=kwargs.get(
                "text", ResponseTextConfig(format=ResponseFormatText(type="text"))
            ),
            truncation=kwargs.get("truncation", "disabled"),
            usage=None,
            user=kwargs.get("user"),
            store=kwargs.get("store", True),
        )
        yield ResponseCreatedEvent(
            response=response,
            type="response.created",
        )
        yield ResponseInProgressEvent(
            response=response,
            type="response.in_progress",
        )
        response.status = "completed"

        for value in events:
            if isinstance(value, ResponseOutputItemDoneEvent):
                response.output.append(value.item)
            elif isinstance(value, IncompleteDetails):
                response.status = "incomplete"
                response.incomplete_details = value
                break
            if isinstance(value, ResponseError):
                response.status = "failed"
                response.error = value
                break

            yield value

            if isinstance(value, ResponseErrorEvent):
                return

        if response.status == "incomplete":
            yield ResponseIncompleteEvent(
                response=response,
                type="response.incomplete",
            )
        elif response.status == "failed":
            yield ResponseFailedEvent(
                response=response,
                type="response.failed",
            )
        else:
            yield ResponseCompletedEvent(
                response=response,
                type="response.completed",
            )

    with patch(
        "openai.resources.responses.AsyncResponses.create",
        AsyncMock(),
    ) as mock_create:
        mock_create.side_effect = lambda **kwargs: mock_generator(
            mock_create.return_value.pop(0), **kwargs
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


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (
            RateLimitError(
                response=httpx.Response(status_code=429, request=""),
                body=None,
                message=None,
            ),
            "Rate limited or insufficient funds",
        ),
        (
            AuthenticationError(
                response=httpx.Response(status_code=401, request=""),
                body=None,
                message=None,
            ),
            "Error talking to OpenAI",
        ),
    ],
)
async def test_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    exception,
    message,
) -> None:
    """Test that we handle errors when calling completion API."""
    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new_callable=AsyncMock,
        side_effect=exception,
    ):
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.speech["plain"]["speech"] == message, result.response.speech


@pytest.mark.parametrize(
    ("reason", "message"),
    [
        (
            "max_output_tokens",
            "max output tokens reached",
        ),
        (
            "content_filter",
            "content filter triggered",
        ),
        (
            None,
            "unknown reason",
        ),
    ],
)
async def test_incomplete_response(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    reason: str,
    message: str,
) -> None:
    """Test handling early model stop."""
    # Incomplete details received after some content is generated
    mock_create_stream.return_value = [
        (
            # Start message
            *create_message_item(
                id="msg_A",
                text=["Once upon", " a time, ", "there was "],
                output_index=0,
            ),
            # Length limit or content filter
            IncompleteDetails(reason=reason),
        )
    ]

    result = await conversation.async_converse(
        hass,
        "Please tell me a big story",
        "mock-conversation-id",
        Context(),
        agent_id="conversation.openai",
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert (
        result.response.speech["plain"]["speech"]
        == f"OpenAI response incomplete: {message}"
    ), result.response.speech

    # Incomplete details received before any content is generated
    mock_create_stream.return_value = [
        (
            # Start generating response
            *create_reasoning_item(id="rs_A", output_index=0),
            # Length limit or content filter
            IncompleteDetails(reason=reason),
        )
    ]

    result = await conversation.async_converse(
        hass,
        "please tell me a big story",
        "mock-conversation-id",
        Context(),
        agent_id="conversation.openai",
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert (
        result.response.speech["plain"]["speech"]
        == f"OpenAI response incomplete: {message}"
    ), result.response.speech


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            ResponseError(code="rate_limit_exceeded", message="Rate limit exceeded"),
            "OpenAI response failed: Rate limit exceeded",
        ),
        (
            ResponseErrorEvent(type="error", message="Some error"),
            "OpenAI response error: Some error",
        ),
    ],
)
async def test_failed_response(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    error: ResponseError | ResponseErrorEvent,
    message: str,
) -> None:
    """Test handling failed and error responses."""
    mock_create_stream.return_value = [(error,)]

    result = await conversation.async_converse(
        hass,
        "next natural number please",
        "mock-conversation-id",
        Context(),
        agent_id="conversation.openai",
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.speech["plain"]["speech"] == message, result.response.speech


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


def create_message_item(
    id: str, text: str | list[str], output_index: int
) -> list[ResponseStreamEvent]:
    """Create a message item."""
    if isinstance(text, str):
        text = [text]

    content = ResponseOutputText(annotations=[], text="", type="output_text")
    events = [
        ResponseOutputItemAddedEvent(
            item=ResponseOutputMessage(
                id=id,
                content=[],
                type="message",
                role="assistant",
                status="in_progress",
            ),
            output_index=output_index,
            type="response.output_item.added",
        ),
        ResponseContentPartAddedEvent(
            content_index=0,
            item_id=id,
            output_index=output_index,
            part=content,
            type="response.content_part.added",
        ),
    ]

    content.text = "".join(text)
    events.extend(
        ResponseTextDeltaEvent(
            content_index=0,
            delta=delta,
            item_id=id,
            output_index=output_index,
            type="response.output_text.delta",
        )
        for delta in text
    )

    events.extend(
        [
            ResponseTextDoneEvent(
                content_index=0,
                item_id=id,
                output_index=output_index,
                text="".join(text),
                type="response.output_text.done",
            ),
            ResponseContentPartDoneEvent(
                content_index=0,
                item_id=id,
                output_index=output_index,
                part=content,
                type="response.content_part.done",
            ),
            ResponseOutputItemDoneEvent(
                item=ResponseOutputMessage(
                    id=id,
                    content=[content],
                    role="assistant",
                    status="completed",
                    type="message",
                ),
                output_index=output_index,
                type="response.output_item.done",
            ),
        ]
    )

    return events


def create_function_tool_call_item(
    id: str, arguments: str | list[str], call_id: str, name: str, output_index: int
) -> list[ResponseStreamEvent]:
    """Create a function tool call item."""
    if isinstance(arguments, str):
        arguments = [arguments]

    events = [
        ResponseOutputItemAddedEvent(
            item=ResponseFunctionToolCall(
                id=id,
                arguments="",
                call_id=call_id,
                name=name,
                type="function_call",
                status="in_progress",
            ),
            output_index=output_index,
            type="response.output_item.added",
        )
    ]

    events.extend(
        ResponseFunctionCallArgumentsDeltaEvent(
            delta=delta,
            item_id=id,
            output_index=output_index,
            type="response.function_call_arguments.delta",
        )
        for delta in arguments
    )

    events.append(
        ResponseFunctionCallArgumentsDoneEvent(
            arguments="".join(arguments),
            item_id=id,
            output_index=output_index,
            type="response.function_call_arguments.done",
        )
    )

    events.append(
        ResponseOutputItemDoneEvent(
            item=ResponseFunctionToolCall(
                id=id,
                arguments="".join(arguments),
                call_id=call_id,
                name=name,
                type="function_call",
                status="completed",
            ),
            output_index=output_index,
            type="response.output_item.done",
        )
    )

    return events


def create_reasoning_item(id: str, output_index: int) -> list[ResponseStreamEvent]:
    """Create a reasoning item."""
    return [
        ResponseOutputItemAddedEvent(
            item=ResponseReasoningItem(
                id=id,
                summary=[],
                type="reasoning",
                status=None,
            ),
            output_index=output_index,
            type="response.output_item.added",
        ),
        ResponseOutputItemDoneEvent(
            item=ResponseReasoningItem(
                id=id,
                summary=[],
                type="reasoning",
                status=None,
            ),
            output_index=output_index,
            type="response.output_item.done",
        ),
    ]


def create_web_search_item(id: str, output_index: int) -> list[ResponseStreamEvent]:
    """Create a web search call item."""
    return [
        ResponseOutputItemAddedEvent(
            item=ResponseFunctionWebSearch(
                id=id, status="in_progress", type="web_search_call"
            ),
            output_index=output_index,
            type="response.output_item.added",
        ),
        ResponseWebSearchCallInProgressEvent(
            item_id=id,
            output_index=output_index,
            type="response.web_search_call.in_progress",
        ),
        ResponseWebSearchCallSearchingEvent(
            item_id=id,
            output_index=output_index,
            type="response.web_search_call.searching",
        ),
        ResponseWebSearchCallCompletedEvent(
            item_id=id,
            output_index=output_index,
            type="response.web_search_call.completed",
        ),
        ResponseOutputItemDoneEvent(
            item=ResponseFunctionWebSearch(
                id=id, status="completed", type="web_search_call"
            ),
            output_index=output_index,
            type="response.output_item.done",
        ),
    ]


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
            # Wait for the model to think
            *create_reasoning_item(id="rs_A", output_index=0),
            # First tool call
            *create_function_tool_call_item(
                id="fc_1",
                arguments=['{"para', 'm1":"call1"}'],
                call_id="call_call_1",
                name="test_tool",
                output_index=1,
            ),
            # Second tool call
            *create_function_tool_call_item(
                id="fc_2",
                arguments='{"param1":"call2"}',
                call_id="call_call_2",
                name="test_tool",
                output_index=2,
            ),
        ),
        # Response after tool responses
        create_message_item(id="msg_A", text="Cool", output_index=0),
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

    assert mock_create_stream.call_args.kwargs["input"][2] == {
        "id": "rs_A",
        "summary": [],
        "type": "reasoning",
    }
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    # Don't test the prompt, as it's not deterministic
    assert mock_chat_log.content[1:] == snapshot


async def test_function_call_without_reasoning(
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
            *create_function_tool_call_item(
                id="fc_1",
                arguments=['{"para', 'm1":"call1"}'],
                call_id="call_call_1",
                name="test_tool",
                output_index=1,
            ),
        ),
        # Response after tool responses
        create_message_item(id="msg_A", text="Cool", output_index=0),
    ]
    mock_chat_log.mock_tool_results(
        {
            "call_call_1": "value1",
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
                *create_function_tool_call_item(
                    id="fc_1",
                    arguments=[],
                    call_id="call_call_1",
                    name="test_tool",
                    output_index=0,
                ),
                *create_message_item(id="msg_A", text="Cool", output_index=1),
            ),
        ),
        (
            "Test invalid JSON",
            (
                *create_function_tool_call_item(
                    id="fc_1",
                    arguments=['{"para'],
                    call_id="call_call_1",
                    name="test_tool",
                    output_index=0,
                ),
                *create_message_item(id="msg_A", text="Cool", output_index=1),
            ),
        ),
    ],
)
async def test_function_call_invalid(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    description: str,
    messages: tuple[ResponseStreamEvent],
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

    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Cool", output_index=0)
    ]

    await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.openai"
    )

    tools = mock_create_stream.mock_calls[0][2]["tools"]
    assert tools


async def test_web_search(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Test web_search_tool."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
            CONF_WEB_SEARCH_USER_LOCATION: True,
            CONF_WEB_SEARCH_CITY: "San Francisco",
            CONF_WEB_SEARCH_COUNTRY: "US",
            CONF_WEB_SEARCH_REGION: "California",
            CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
        },
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    message = "Home Assistant now supports ChatGPT Search in Assist"
    mock_create_stream.return_value = [
        # Initial conversation
        (
            *create_web_search_item(id="ws_A", output_index=0),
            *create_message_item(id="msg_A", text=message, output_index=1),
        )
    ]

    result = await conversation.async_converse(
        hass,
        "What's on the latest news?",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.openai",
    )

    assert mock_create_stream.mock_calls[0][2]["tools"] == [
        {
            "type": "web_search_preview",
            "search_context_size": "low",
            "user_location": {
                "type": "approximate",
                "city": "San Francisco",
                "region": "California",
                "country": "US",
                "timezone": "America/Los_Angeles",
            },
        }
    ]
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == message, result.response.speech
