"""Tests for the Azure OpenAI integration."""

import datetime
from typing import Literal
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
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
from syrupy.filters import props

from homeassistant.components import conversation
from homeassistant.components.azure_openai.const import (
    CONF_CHAT_MODEL,
    CONF_CODE_INTERPRETER,
    CONF_MODEL_FAMILY,
    CONF_PRO_MODE,
    CONF_REASONING_EFFORT,
    CONF_REASONING_SUMMARY,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_VERBOSITY,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_INLINE_CITATIONS,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
)
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.intent import async_register_timer_handler
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.llm import ToolInput, ToolResult
from homeassistant.setup import async_setup_component

from . import (
    create_code_interpreter_item,
    create_function_tool_call_item,
    create_message_item,
    create_reasoning_item,
    create_web_search_item,
)
from .conftest import MOCK_CHAT_DEPLOYMENT

from tests.common import MockConfigEntry
from tests.components.conversation import MockChatLog

CONVERSATION_ENTITY_ID = "conversation.azure_openai_conversation"


def assert_response_models(
    mock_create_stream: AsyncMock,
    expected_model: str,
    expected_calls: int | None = None,
) -> None:
    """Assert every responses.create call used the configured deployment."""
    if expected_calls is not None:
        assert mock_create_stream.call_count == expected_calls
    assert mock_create_stream.call_count > 0
    for mock_call in mock_create_stream.mock_calls:
        assert mock_call.kwargs["model"] == expected_model


def get_conversation_subentry(
    mock_config_entry: MockConfigEntry,
) -> ConfigSubentry:
    """Return the conversation subentry for the config entry."""
    return next(
        subentry
        for subentry in mock_config_entry.subentries.values()
        if subentry.subentry_type == "conversation"
    )


async def test_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test entity properties."""
    state = hass.states.get(CONVERSATION_ENTITY_ID)
    assert state
    assert state.attributes["supported_features"] == 0

    subentry = get_conversation_subentry(mock_config_entry)
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_LLM_HASS_API: "assist"},
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    state = hass.states.get(CONVERSATION_ENTITY_ID)
    assert state
    assert (
        state.attributes["supported_features"]
        == conversation.ConversationEntityFeature.CONTROL
    )


@pytest.mark.parametrize(
    ("exception", "message", "expected_reauth_calls"),
    [
        (
            RateLimitError(
                response=httpx.Response(status_code=429, request=""),
                body=None,
                message=None,
            ),
            "Rate limited or insufficient funds",
            0,
        ),
        (
            AuthenticationError(
                response=httpx.Response(status_code=401, request=""),
                body=None,
                message=None,
            ),
            "Error talking to Azure OpenAI",
            1,
        ),
    ],
)
async def test_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    mock_create_stream: AsyncMock,
    exception: AuthenticationError | RateLimitError,
    message: str,
    expected_reauth_calls: int,
) -> None:
    """Test that we handle errors when calling completion API."""
    mock_create_stream.return_value = [exception]

    with patch.object(mock_config_entry, "async_start_reauth") as mock_reauth:
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type is intent.IntentResponseType.ERROR, result
    assert result.response.speech["plain"]["speech"] == message, result.response.speech
    assert mock_reauth.call_count == expected_reauth_calls
    assert_response_models(mock_create_stream, MOCK_CHAT_DEPLOYMENT)


@pytest.mark.usefixtures("mock_chat_log")
async def test_llm_data_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test errors while preparing LLM data are returned."""
    response = intent.IntentResponse(language="en")
    response.async_set_error(
        intent.IntentResponseErrorCode.UNKNOWN,
        "Unable to prepare LLM data",
    )
    with patch.object(
        MockChatLog,
        "async_provide_llm_data",
        new=AsyncMock(
            side_effect=conversation.ConverseError(
                "Unable to prepare LLM data",
                "mock-conversation-id",
                response,
            )
        ),
    ):
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.speech["plain"]["speech"] == "Unable to prepare LLM data"


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
    mock_init_component: None,
    mock_create_stream: AsyncMock,
    reason: str,
    message: str,
) -> None:
    """Test handling early model stop."""
    mock_create_stream.return_value = [
        (
            *create_message_item(
                id="msg_A",
                text=["Once upon", " a time, ", "there was "],
                output_index=0,
            ),
            IncompleteDetails(reason=reason),
        )
    ]

    result = await conversation.async_converse(
        hass,
        "Please tell me a big story",
        "mock-conversation-id",
        Context(),
        agent_id=CONVERSATION_ENTITY_ID,
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR, result
    assert (
        result.response.speech["plain"]["speech"]
        == f"Azure OpenAI response incomplete: {message}"
    ), result.response.speech

    mock_create_stream.return_value = [
        (
            *create_reasoning_item(id="rs_A", output_index=0),
            IncompleteDetails(reason=reason),
        )
    ]

    result = await conversation.async_converse(
        hass,
        "please tell me a big story",
        "mock-conversation-id",
        Context(),
        agent_id=CONVERSATION_ENTITY_ID,
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR, result
    assert (
        result.response.speech["plain"]["speech"]
        == f"Azure OpenAI response incomplete: {message}"
    ), result.response.speech
    assert_response_models(mock_create_stream, MOCK_CHAT_DEPLOYMENT, expected_calls=2)


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            ResponseError(code="rate_limit_exceeded", message="Rate limit exceeded"),
            "Azure OpenAI response failed: Rate limit exceeded",
        ),
        (
            ResponseErrorEvent(type="error", message="Some error", sequence_number=0),
            "Azure OpenAI response error: Some error",
        ),
    ],
)
async def test_failed_response(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component: None,
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
        agent_id=CONVERSATION_ENTITY_ID,
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR, result
    assert result.response.speech["plain"]["speech"] == message, result.response.speech
    assert_response_models(mock_create_stream, MOCK_CHAT_DEPLOYMENT)


async def test_conversation_agent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test OpenAIAgent."""
    agent = conversation.get_agent_manager(hass).async_get_agent(
        mock_config_entry.entry_id
    )
    assert agent.supported_languages == "*"


@freeze_time("2025-10-31 12:00:00")
async def test_function_call(
    hass: HomeAssistant,
    mock_config_entry_with_reasoning_model: MockConfigEntry,
    mock_init_component: None,
    mock_create_stream: AsyncMock,
    mock_chat_log: MockChatLog,
    snapshot: SnapshotAssertion,
) -> None:
    """Test function call from the assistant."""

    mock_chat_log.async_add_user_content(
        conversation.UserContent(content="What time is it?")
    )
    mock_chat_log.async_add_assistant_content_without_tools(
        conversation.AssistantContent(
            agent_id=CONVERSATION_ENTITY_ID,
            tool_calls=[
                ToolInput(
                    tool_name="HassGetCurrentTime",
                    tool_args={},
                    id="mock-tool-call-id",
                    external=True,
                )
            ],
        )
    )
    mock_chat_log.async_add_assistant_content_without_tools(
        conversation.ToolResultContent(
            agent_id=CONVERSATION_ENTITY_ID,
            tool_call_id="mock-tool-call-id",
            tool_name="HassGetCurrentTime",
            result=ToolResult(
                data={
                    "speech": {"plain": {"speech": "12:00 PM", "extra_data": None}},
                    "response_type": "action_done",
                    "speech_slots": {"time": datetime.time(12, 0, 0, 0)},
                    "data": {"success": [], "failed": []},
                }
            ),
        )
    )
    mock_chat_log.async_add_assistant_content_without_tools(
        conversation.AssistantContent(
            agent_id=CONVERSATION_ENTITY_ID,
            content="12:00 PM",
        )
    )

    mock_create_stream.return_value = [
        (
            *create_reasoning_item(
                id="rs_A",
                output_index=0,
                reasoning_summary=[["Thinking"], ["Thinking ", "more"]],
            ),
            *create_function_tool_call_item(
                id="fc_1",
                arguments=['{"para', 'm1":"call1"}'],
                call_id="call_call_1",
                name="test_tool",
                output_index=1,
            ),
            *create_function_tool_call_item(
                id="fc_2",
                arguments='{"param1":"call2"}',
                call_id="call_call_2",
                name="test_tool",
                output_index=2,
            ),
        ),
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
        agent_id=CONVERSATION_ENTITY_ID,
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    # The generated prompt is nondeterministic.
    assert mock_chat_log.content[1:] == snapshot
    assert mock_create_stream.call_args.kwargs["input"][1:] == snapshot
    assert_response_models(mock_create_stream, MOCK_CHAT_DEPLOYMENT, expected_calls=2)


@freeze_time("2025-10-31 18:00:00")
async def test_function_call_without_reasoning(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component: None,
    mock_create_stream: AsyncMock,
    mock_chat_log: MockChatLog,
    snapshot: SnapshotAssertion,
) -> None:
    """Test function call from the assistant."""
    mock_create_stream.return_value = [
        (
            *create_function_tool_call_item(
                id="fc_1",
                arguments=['{"para', 'm1":"call1"}'],
                call_id="call_call_1",
                name="test_tool",
                output_index=1,
            ),
        ),
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
        agent_id=CONVERSATION_ENTITY_ID,
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    # The generated prompt is nondeterministic.
    assert mock_chat_log.content[1:] == snapshot
    assert_response_models(mock_create_stream, MOCK_CHAT_DEPLOYMENT, expected_calls=2)


async def test_interleaved_parallel_function_calls(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component: None,
    mock_create_stream: AsyncMock,
    mock_chat_log: MockChatLog,
) -> None:
    """Test interleaved argument deltas remain assigned to their tool calls."""
    first_call = create_function_tool_call_item(
        id="fc_1",
        arguments=['{"para', 'm1":"call1"}'],
        call_id="call_call_1",
        name="test_tool",
        output_index=0,
    )
    second_call = create_function_tool_call_item(
        id="fc_2",
        arguments=['{"para', 'm1":"call2"}'],
        call_id="call_call_2",
        name="test_tool",
        output_index=1,
    )
    mock_create_stream.return_value = [
        (
            first_call[0],
            second_call[0],
            first_call[1],
            second_call[1],
            first_call[2],
            second_call[2],
            first_call[3],
            second_call[3],
            first_call[4],
            second_call[4],
        ),
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
        "Please call the test function twice",
        mock_chat_log.conversation_id,
        Context(),
        agent_id=CONVERSATION_ENTITY_ID,
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    tool_calls = [
        tool_call
        for content in mock_chat_log.content
        if isinstance(content, conversation.AssistantContent)
        for tool_call in content.tool_calls or []
    ]
    assert [(tool_call.id, tool_call.tool_args) for tool_call in tool_calls] == [
        ("call_call_1", {"param1": "call1"}),
        ("call_call_2", {"param1": "call2"}),
    ]


@freeze_time("2025-10-31 18:00:00")
async def test_reasoning_summary_off_omits_summary_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    mock_create_stream: AsyncMock,
    mock_chat_log: MockChatLog,
) -> None:
    """Test that reasoning summary 'off' omits the summary key from the API call."""
    conversation_subentry = get_conversation_subentry(mock_config_entry)
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        conversation_subentry,
        data={
            **conversation_subentry.data,
            CONF_CHAT_MODEL: MOCK_CHAT_DEPLOYMENT,
            CONF_MODEL_FAMILY: "o4-mini",
            CONF_REASONING_SUMMARY: "off",
        },
    )
    await hass.async_block_till_done()

    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Hello", output_index=0),
    ]

    await conversation.async_converse(
        hass,
        "Hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id=CONVERSATION_ENTITY_ID,
    )

    reasoning = mock_create_stream.call_args.kwargs["reasoning"]
    assert "summary" not in reasoning
    assert_response_models(mock_create_stream, MOCK_CHAT_DEPLOYMENT)


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
    mock_init_component: None,
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
            agent_id=CONVERSATION_ENTITY_ID,
        )

    assert_response_models(mock_create_stream, MOCK_CHAT_DEPLOYMENT)


async def test_assist_api_tools_conversion(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component: None,
    mock_create_stream: AsyncMock,
) -> None:
    """Test that we are able to convert actual tools from Assist API."""
    for domain in (
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
        assert await async_setup_component(hass, domain, {})
        hass.states.async_set(f"{domain}.test", "on")
        async_expose_entity(hass, "conversation", f"{domain}.test", True)

    async_register_timer_handler(hass, "test_device", lambda *args: None)

    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Cool", output_index=0)
    ]

    await conversation.async_converse(
        hass,
        "hello",
        None,
        Context(),
        agent_id=CONVERSATION_ENTITY_ID,
        device_id="test_device",
    )

    tools = mock_create_stream.mock_calls[0][2]["tools"]
    assert tools

    assert_response_models(mock_create_stream, MOCK_CHAT_DEPLOYMENT)

    for tool in tools:
        msg = (
            f"Invalid schema for function '{tool['name']}': schema must have type "
            "'object' and not have 'oneOf'/'anyOf'/'allOf'/"
            "'enum'/'not' at the top level."
        )
        assert tool["parameters"]["type"] == "object", msg
        for key in ("oneOf", "anyOf", "allOf", "enum", "not"):
            assert key not in tool["parameters"], msg


async def test_conversation_agent_does_not_store_responses(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    mock_create_stream: AsyncMock,
) -> None:
    """Test conversation responses are not stored by Azure OpenAI."""
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Hello!", output_index=0)
    ]

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert mock_create_stream.call_args is not None
    assert mock_create_stream.call_args.kwargs["store"] is False
    assert_response_models(mock_create_stream, MOCK_CHAT_DEPLOYMENT)


@pytest.mark.parametrize("inline_citations", [True, False])
async def test_web_search(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    mock_create_stream: AsyncMock,
    mock_chat_log: MockChatLog,
    snapshot: SnapshotAssertion,
    inline_citations: bool,
) -> None:
    """Test web_search_tool."""
    subentry = get_conversation_subentry(mock_config_entry)
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

    message = [
        "Home Assistant now supports ",
        "ChatGPT Search in Assist",
        " ([release notes](https://www.home-assistant.io/blog/categories/release-notes/)",
        ").",
    ]
    mock_create_stream.return_value = [
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
        agent_id=CONVERSATION_ENTITY_ID,
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
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    mock_create_stream.return_value = [
        (*create_message_item(id="msg_B", text="You are welcome!", output_index=1),)
    ]

    result = await conversation.async_converse(
        hass,
        "Thank you!",
        mock_chat_log.conversation_id,
        Context(),
        agent_id=CONVERSATION_ENTITY_ID,
    )

    assert (
        isinstance(mock_create_stream.mock_calls[0][2]["input"][0]["content"], list)
        and "do not include source citations"
        in mock_create_stream.mock_calls[0][2]["input"][0]["content"][1]["text"]
    ) is not inline_citations
    assert mock_create_stream.mock_calls[1][2]["input"][1:] == snapshot
    assert_response_models(mock_create_stream, MOCK_CHAT_DEPLOYMENT, expected_calls=2)


async def test_web_search_remove_citations_gpt5(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    mock_create_stream: AsyncMock,
    mock_chat_log: MockChatLog,
) -> None:
    """Test that citations are stripped for GPT-5 models with inline_citations disabled."""
    subentry = get_conversation_subentry(mock_config_entry)
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_CHAT_MODEL: MOCK_CHAT_DEPLOYMENT,
            CONF_MODEL_FAMILY: "gpt-5-mini",
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_INLINE_CITATIONS: False,
        },
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    message = [
        "The match ended 0-2",
        " ([legaseriea.it](https://www.legaseriea.it/))",
        ".",
    ]
    mock_create_stream.return_value = [
        (
            *create_web_search_item(id="ws_A", output_index=0),
            *create_message_item(id="msg_A", text=message, output_index=1),
        )
    ]

    result = await conversation.async_converse(
        hass,
        "What was the score?",
        mock_chat_log.conversation_id,
        Context(),
        agent_id=CONVERSATION_ENTITY_ID,
    )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "The match ended 0-2."
    assert_response_models(mock_create_stream, MOCK_CHAT_DEPLOYMENT)


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    "status",
    [
        pytest.param("completed", id="completed"),
        pytest.param("incomplete", id="incomplete"),
        pytest.param("failed", id="failed"),
    ],
)
async def test_code_interpreter(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    mock_chat_log: MockChatLog,
    snapshot: SnapshotAssertion,
    status: Literal["completed", "incomplete", "failed"],
) -> None:
    """Test code_interpreter tool."""
    subentry = get_conversation_subentry(mock_config_entry)
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_CODE_INTERPRETER: True,
        },
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    message = (
        "I’ve calculated it with Python: the square root of"
        " 55555 is approximately 235.70108188126758."
    )
    mock_create_stream.return_value = [
        (
            *create_code_interpreter_item(
                id="ci_A",
                code=["import", " math", "\n", "math", ".sqrt", "(", "555", "55", ")"],
                logs="235.70108188126758\n",
                output_index=0,
                status=status,
            ),
            *create_message_item(id="msg_A", text=message, output_index=1),
        )
    ]

    result = await conversation.async_converse(
        hass,
        "Please use the python tool to calculate square root of 55555",
        mock_chat_log.conversation_id,
        Context(),
        agent_id=CONVERSATION_ENTITY_ID,
    )

    assert mock_create_stream.mock_calls[0][2]["tools"] == [
        {"type": "code_interpreter", "container": {"type": "auto"}}
    ]
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == message, result.response.speech

    assistant_content = mock_chat_log.content[2]
    assert isinstance(assistant_content, conversation.AssistantContent)
    assert assistant_content.tool_calls
    assert assistant_content.tool_calls[0].tool_args == {
        "code": "import math\nmath.sqrt(55555)"
    }
    tool_result = mock_chat_log.content[3]
    assert isinstance(tool_result, conversation.ToolResultContent)
    assert tool_result.result.data["container_id"] == "cntr_A"

    mock_create_stream.return_value = [
        (*create_message_item(id="msg_B", text="You are welcome!", output_index=1),)
    ]

    result = await conversation.async_converse(
        hass,
        "Thank you!",
        mock_chat_log.conversation_id,
        Context(),
        agent_id=CONVERSATION_ENTITY_ID,
    )

    request_input = mock_create_stream.mock_calls[1][2]["input"][1:]
    assert request_input[1]["outputs"][0]["logs"] == "235.70108188126758\n"
    assert request_input == snapshot(exclude=props("logs"))
    assert mock_create_stream.mock_calls[1][2]["tools"] == [
        {"type": "code_interpreter", "container": {"type": "auto"}}
    ]
    assert mock_create_stream.mock_calls[1][2]["input"][2]["status"] == status
    assert_response_models(mock_create_stream, MOCK_CHAT_DEPLOYMENT, expected_calls=2)


async def test_unknown_model_family_uses_basic_capabilities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    mock_create_stream: AsyncMock,
) -> None:
    """Test unknown families fall back to conservative request shaping."""
    subentry = get_conversation_subentry(mock_config_entry)
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_CHAT_MODEL: "custom-deployment",
            CONF_MODEL_FAMILY: "custom-family",
            CONF_CODE_INTERPRETER: True,
            CONF_PRO_MODE: True,
            CONF_REASONING_EFFORT: "high",
            CONF_REASONING_SUMMARY: "detailed",
            CONF_VERBOSITY: "high",
            CONF_WEB_SEARCH: True,
        },
    )
    await hass.async_block_till_done()

    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Hi!", output_index=0),
    ]

    await conversation.async_converse(
        hass,
        "Hello",
        None,
        Context(),
        agent_id=CONVERSATION_ENTITY_ID,
    )

    model_args = mock_create_stream.call_args.kwargs
    assert model_args["model"] == "custom-deployment"
    assert model_args["temperature"] == 1.0
    assert model_args["top_p"] == 1.0
    assert "reasoning" not in model_args
    assert "include" not in model_args
    assert "text" not in model_args
    assert "tools" not in model_args
    assert "prompt_cache_options" not in model_args
    assert "prompt_cache_retention" not in model_args


@pytest.mark.parametrize(
    ("subentry_options", "expected_model"),
    [
        pytest.param(
            {
                CONF_CHAT_MODEL: "basic-deployment",
                CONF_MODEL_FAMILY: "gpt-4o-mini",
            },
            "basic-deployment",
            id="basic-family",
        ),
        pytest.param(
            {
                CONF_CHAT_MODEL: "gpt55-deployment",
                CONF_MODEL_FAMILY: "gpt-5.5",
            },
            "gpt55-deployment",
            id="reasoning-verbosity-cache24",
        ),
        pytest.param(
            {
                CONF_CHAT_MODEL: "gpt56-pro-deployment",
                CONF_MODEL_FAMILY: "gpt-5.6-sol",
                CONF_PRO_MODE: True,
            },
            "gpt56-pro-deployment",
            id="pro-mode",
        ),
        pytest.param(
            {
                CONF_CHAT_MODEL: "gpt56-sampling-deployment",
                CONF_MODEL_FAMILY: "gpt-5.6-sol",
                CONF_REASONING_EFFORT: "none",
                CONF_TEMPERATURE: 0.5,
                CONF_TOP_P: 0.9,
            },
            "gpt56-sampling-deployment",
            id="sampling-none",
        ),
        pytest.param(
            {
                CONF_CHAT_MODEL: "gpt6-default-deployment",
                CONF_MODEL_FAMILY: "gpt-6-astra",
            },
            "gpt6-default-deployment",
            id="gpt6-default",
        ),
        pytest.param(
            {
                CONF_CHAT_MODEL: "gpt6-pro-deployment",
                CONF_MODEL_FAMILY: "gpt-6-astra",
                CONF_REASONING_EFFORT: "max",
                CONF_PRO_MODE: True,
                CONF_REASONING_SUMMARY: "detailed",
                CONF_VERBOSITY: "low",
                CONF_TEMPERATURE: 0.5,
                CONF_TOP_P: 0.9,
            },
            "gpt6-pro-deployment",
            id="gpt6-pro",
        ),
        pytest.param(
            {
                CONF_CHAT_MODEL: "gpt6-summary-off-deployment",
                CONF_MODEL_FAMILY: "gpt-6-astra",
                CONF_REASONING_EFFORT: "high",
                CONF_REASONING_SUMMARY: "off",
                CONF_VERBOSITY: "high",
            },
            "gpt6-summary-off-deployment",
            id="gpt6-summary-off",
        ),
    ],
)
@pytest.mark.usefixtures("mock_init_component")
async def test_model_args(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    snapshot: SnapshotAssertion,
    subentry_options: dict[str, str | bool | float],
    expected_model: str,
) -> None:
    """Test model arguments for various configuration."""

    subentry = get_conversation_subentry(mock_config_entry)
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, **subentry_options},
    )
    await hass.async_block_till_done()

    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Hi!", output_index=0),
    ]

    await conversation.async_converse(
        hass,
        "Hello",
        None,
        Context(),
        agent_id=CONVERSATION_ENTITY_ID,
    )

    model_args = mock_create_stream.call_args.kwargs.copy()
    model_args.pop("input")
    assert "safety_identifier" not in model_args
    assert model_args.pop("prompt_cache_key") == subentry.subentry_id
    assert model_args["model"] == expected_model
    assert model_args == snapshot
