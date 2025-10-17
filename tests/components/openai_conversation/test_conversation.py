"""Tests for the OpenAI integration."""

from unittest.mock import AsyncMock, patch

import httpx
from openai import AuthenticationError, RateLimitError
from openai.types.responses import (
    ResponseError,
    ResponseErrorEvent,
    ResponseStreamEvent,
)
from openai.types.responses.response import IncompleteDetails
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.openai_conversation.const import (
    CONF_CODE_INTERPRETER,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_INLINE_CITATIONS,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from . import (
    create_code_interpreter_item,
    create_function_tool_call_item,
    create_message_item,
    create_reasoning_item,
    create_web_search_item,
)

from tests.common import MockConfigEntry
from tests.components.conversation import (
    MockChatLog,
    mock_chat_log,  # noqa: F401
)


async def test_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test entity properties."""
    state = hass.states.get("conversation.openai_conversation")
    assert state
    assert state.attributes["supported_features"] == 0

    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={CONF_LLM_HASS_API: "assist"},
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    state = hass.states.get("conversation.openai_conversation")
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
        agent_id="conversation.openai_conversation",
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
        agent_id="conversation.openai_conversation",
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
            ResponseErrorEvent(type="error", message="Some error", sequence_number=0),
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
        agent_id="conversation.openai_conversation",
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


async def test_function_call(
    hass: HomeAssistant,
    mock_config_entry_with_reasoning_model: MockConfigEntry,
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
            *create_reasoning_item(
                id="rs_A",
                output_index=0,
                reasoning_summary=[["Thinking"], ["Thinking ", "more"]],
            ),
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
        agent_id="conversation.openai_conversation",
    )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    # Don't test the prompt, as it's not deterministic
    assert mock_chat_log.content[1:] == snapshot
    assert mock_create_stream.call_args.kwargs["input"][1:] == snapshot


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
        agent_id="conversation.openai_conversation",
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
            agent_id="conversation.openai_conversation",
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
        hass, "hello", None, Context(), agent_id="conversation.openai_conversation"
    )

    tools = mock_create_stream.mock_calls[0][2]["tools"]
    assert tools


@pytest.mark.parametrize("inline_citations", [True, False])
async def test_web_search(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream,
    mock_chat_log: MockChatLog,  # noqa: F811
    snapshot: SnapshotAssertion,
    inline_citations: bool,
) -> None:
    """Test web_search_tool."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_CONTEXT_SIZE: "low",
            CONF_WEB_SEARCH_USER_LOCATION: True,
            CONF_WEB_SEARCH_CITY: "San Francisco",
            CONF_WEB_SEARCH_COUNTRY: "US",
            CONF_WEB_SEARCH_REGION: "California",
            CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
            CONF_WEB_SEARCH_INLINE_CITATIONS: inline_citations,
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
        agent_id="conversation.openai_conversation",
    )

    assert mock_create_stream.mock_calls[0][2]["tools"] == [
        {
            "type": "web_search",
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

    # Test follow-up message in multi-turn conversation
    mock_create_stream.return_value = [
        (*create_message_item(id="msg_B", text="You are welcome!", output_index=1),)
    ]

    result = await conversation.async_converse(
        hass,
        "Thank you!",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.openai_conversation",
    )

    assert (
        "do not include source citations"
        in mock_create_stream.mock_calls[0][2]["input"][0]["content"]
    ) is not inline_citations
    assert mock_create_stream.mock_calls[1][2]["input"][1:] == snapshot


async def test_code_interpreter(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream,
    mock_chat_log: MockChatLog,  # noqa: F811
    snapshot: SnapshotAssertion,
) -> None:
    """Test code_interpreter tool."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_CODE_INTERPRETER: True,
        },
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    message = "I’ve calculated it with Python: the square root of 55555 is approximately 235.70108188126758."
    mock_create_stream.return_value = [
        (
            *create_code_interpreter_item(
                id="ci_A",
                code=["import", " math", "\n", "math", ".sqrt", "(", "555", "55", ")"],
                logs="235.70108188126758\n",
                output_index=0,
            ),
            *create_message_item(id="msg_A", text=message, output_index=1),
        )
    ]

    result = await conversation.async_converse(
        hass,
        "Please use the python tool to calculate square root of 55555",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.openai_conversation",
    )

    assert mock_create_stream.mock_calls[0][2]["tools"] == [
        {"type": "code_interpreter", "container": {"type": "auto"}}
    ]
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == message, result.response.speech

    # Test follow-up message in multi-turn conversation
    mock_create_stream.return_value = [
        (*create_message_item(id="msg_B", text="You are welcome!", output_index=1),)
    ]

    result = await conversation.async_converse(
        hass,
        "Thank you!",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.openai_conversation",
    )

    assert mock_create_stream.mock_calls[1][2]["input"][1:] == snapshot
