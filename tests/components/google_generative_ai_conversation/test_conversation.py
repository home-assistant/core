"""Tests for the Google Generative AI Conversation integration conversation platform."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from freezegun import freeze_time
from google.genai.types import FunctionCall
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.conversation import UserContent, async_get_chat_log, trace
from homeassistant.components.google_generative_ai_conversation.conversation import (
    ERROR_GETTING_RESPONSE,
    _escape_decode,
    _format_schema,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import chat_session, intent, llm

from . import CLIENT_ERROR_500

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def freeze_the_time():
    """Freeze the time."""
    with freeze_time("2024-05-24 12:00:00", tz_offset=0):
        yield


@pytest.fixture(autouse=True)
def mock_ulid_tools():
    """Mock generated ULIDs for tool calls."""
    with patch("homeassistant.helpers.llm.ulid_now", return_value="mock-tool-call"):
        yield


@patch(
    "homeassistant.components.google_generative_ai_conversation.conversation.llm.AssistAPI._async_get_tools"
)
@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.usefixtures("mock_ulid_tools")
async def test_function_call(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test function calling."""
    agent_id = "conversation.google_generative_ai_conversation"
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {
            vol.Optional("param1", description="Test parameters"): [
                vol.All(str, vol.Lower)
            ],
            vol.Optional("param2"): vol.Any(float, int),
            vol.Optional("param3"): dict,
        }
    )

    mock_get_tools.return_value = [mock_tool]

    with patch("google.genai.chats.AsyncChats.create") as mock_create:
        mock_chat = AsyncMock()
        mock_create.return_value.send_message = mock_chat
        chat_response = Mock(prompt_feedback=None)
        mock_chat.return_value = chat_response
        mock_part = Mock()
        mock_part.text = ""
        mock_part.function_call = FunctionCall(
            name="test_tool",
            args={
                "param1": ["test_value", "param1\\'s value"],
                "param2": 2.7,
            },
        )

        def tool_call(
            hass: HomeAssistant, tool_input: llm.ToolInput, tool_context: llm.LLMContext
        ) -> dict[str, Any]:
            mock_part.function_call = None
            mock_part.text = "Hi there!"
            return {"result": "Test response"}

        mock_tool.async_call.side_effect = tool_call
        chat_response.candidates = [Mock(content=Mock(parts=[mock_part]))]
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
            device_id="test_device",
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.as_dict()["speech"]["plain"]["speech"] == "Hi there!"
    mock_tool_response_parts = mock_create.mock_calls[2][2]["message"]
    assert len(mock_tool_response_parts) == 1
    assert mock_tool_response_parts[0].model_dump() == {
        "code_execution_result": None,
        "executable_code": None,
        "file_data": None,
        "function_call": None,
        "function_response": {
            "id": None,
            "name": "test_tool",
            "response": {
                "result": "Test response",
            },
        },
        "inline_data": None,
        "text": None,
        "thought": None,
        "video_metadata": None,
    }

    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
            id="mock-tool-call",
            tool_name="test_tool",
            tool_args={
                "param1": ["test_value", "param1's value"],
                "param2": 2.7,
            },
        ),
        llm.LLMContext(
            platform="google_generative_ai_conversation",
            context=context,
            user_prompt="Please call the test function",
            language="en",
            assistant="conversation",
            device_id="test_device",
        ),
    )
    assert [tuple(mock_call) for mock_call in mock_create.mock_calls] == snapshot

    # Test conversating tracing
    traces = trace.async_get_traces()
    assert traces
    last_trace = traces[-1].as_dict()
    trace_events = last_trace.get("events", [])
    assert [event["event_type"] for event in trace_events] == [
        trace.ConversationTraceEventType.ASYNC_PROCESS,
        trace.ConversationTraceEventType.AGENT_DETAIL,  # prompt and tools
        trace.ConversationTraceEventType.AGENT_DETAIL,  # stats for response
        trace.ConversationTraceEventType.TOOL_CALL,
        trace.ConversationTraceEventType.AGENT_DETAIL,  # stats for response
    ]
    # AGENT_DETAIL event contains the raw prompt passed to the model
    detail_event = trace_events[1]
    assert "Answer in plain text" in detail_event["data"]["messages"][0]["content"]
    assert [
        p["tool_name"] for p in detail_event["data"]["messages"][2]["tool_calls"]
    ] == ["test_tool"]

    detail_event = trace_events[2]
    assert set(detail_event["data"]["stats"].keys()) == {
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
    }


@patch(
    "homeassistant.components.google_generative_ai_conversation.conversation.llm.AssistAPI._async_get_tools"
)
@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.usefixtures("mock_ulid_tools")
async def test_use_google_search(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_google_search: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test function calling."""
    agent_id = "conversation.google_generative_ai_conversation"
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {
            vol.Optional("param1", description="Test parameters"): [
                vol.All(str, vol.Lower)
            ],
            vol.Optional("param2"): vol.Any(float, int),
            vol.Optional("param3"): dict,
        }
    )

    mock_get_tools.return_value = [mock_tool]

    with patch("google.genai.chats.AsyncChats.create") as mock_create:
        mock_chat = AsyncMock()
        mock_create.return_value.send_message = mock_chat
        chat_response = Mock(prompt_feedback=None)
        mock_chat.return_value = chat_response
        mock_part = Mock()
        mock_part.text = ""
        mock_part.function_call = FunctionCall(
            name="test_tool",
            args={
                "param1": ["test_value", "param1\\'s value"],
                "param2": 2.7,
            },
        )

        def tool_call(
            hass: HomeAssistant, tool_input: llm.ToolInput, tool_context: llm.LLMContext
        ) -> dict[str, Any]:
            mock_part.function_call = None
            mock_part.text = "Hi there!"
            return {"result": "Test response"}

        mock_tool.async_call.side_effect = tool_call
        chat_response.candidates = [Mock(content=Mock(parts=[mock_part]))]
        await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
            device_id="test_device",
        )

    assert [tuple(mock_call) for mock_call in mock_create.mock_calls] == snapshot


@patch(
    "homeassistant.components.google_generative_ai_conversation.conversation.llm.AssistAPI._async_get_tools"
)
@pytest.mark.usefixtures("mock_init_component")
async def test_function_call_without_parameters(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test function calling without parameters."""
    agent_id = "conversation.google_generative_ai_conversation"
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema({})

    mock_get_tools.return_value = [mock_tool]

    with patch("google.genai.chats.AsyncChats.create") as mock_create:
        mock_chat = AsyncMock()
        mock_create.return_value.send_message = mock_chat
        chat_response = Mock(prompt_feedback=None)
        mock_chat.return_value = chat_response
        mock_part = Mock()
        mock_part.text = ""
        mock_part.function_call = FunctionCall(name="test_tool", args={})

        def tool_call(
            hass: HomeAssistant, tool_input: llm.ToolInput, tool_context: llm.LLMContext
        ) -> dict[str, Any]:
            mock_part.function_call = None
            mock_part.text = "Hi there!"
            return {"result": "Test response"}

        mock_tool.async_call.side_effect = tool_call
        chat_response.candidates = [Mock(content=Mock(parts=[mock_part]))]
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
            device_id="test_device",
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.as_dict()["speech"]["plain"]["speech"] == "Hi there!"
    mock_tool_response_parts = mock_create.mock_calls[2][2]["message"]
    assert len(mock_tool_response_parts) == 1
    assert mock_tool_response_parts[0].model_dump() == {
        "code_execution_result": None,
        "executable_code": None,
        "file_data": None,
        "function_call": None,
        "function_response": {
            "id": None,
            "name": "test_tool",
            "response": {
                "result": "Test response",
            },
        },
        "inline_data": None,
        "text": None,
        "thought": None,
        "video_metadata": None,
    }

    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
            id="mock-tool-call",
            tool_name="test_tool",
            tool_args={},
        ),
        llm.LLMContext(
            platform="google_generative_ai_conversation",
            context=context,
            user_prompt="Please call the test function",
            language="en",
            assistant="conversation",
            device_id="test_device",
        ),
    )
    assert [tuple(mock_call) for mock_call in mock_create.mock_calls] == snapshot


@patch(
    "homeassistant.components.google_generative_ai_conversation.conversation.llm.AssistAPI._async_get_tools"
)
@pytest.mark.usefixtures("mock_init_component")
async def test_function_exception(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
) -> None:
    """Test exception in function calling."""
    agent_id = "conversation.google_generative_ai_conversation"
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {
            vol.Optional("param1", description="Test parameters"): vol.All(
                vol.Coerce(int), vol.Range(0, 100)
            )
        }
    )

    mock_get_tools.return_value = [mock_tool]

    with patch("google.genai.chats.AsyncChats.create") as mock_create:
        mock_chat = AsyncMock()
        mock_create.return_value.send_message = mock_chat
        chat_response = Mock(prompt_feedback=None)
        mock_chat.return_value = chat_response
        mock_part = Mock()
        mock_part.text = ""
        mock_part.function_call = FunctionCall(name="test_tool", args={"param1": 1})

        def tool_call(
            hass: HomeAssistant, tool_input: llm.ToolInput, tool_context: llm.LLMContext
        ) -> dict[str, Any]:
            mock_part.function_call = None
            mock_part.text = "Hi there!"
            raise HomeAssistantError("Test tool exception")

        mock_tool.async_call.side_effect = tool_call
        chat_response.candidates = [Mock(content=Mock(parts=[mock_part]))]
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
            device_id="test_device",
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.as_dict()["speech"]["plain"]["speech"] == "Hi there!"
    mock_tool_response_parts = mock_create.mock_calls[2][2]["message"]
    assert len(mock_tool_response_parts) == 1
    assert mock_tool_response_parts[0].model_dump() == {
        "code_execution_result": None,
        "executable_code": None,
        "file_data": None,
        "function_call": None,
        "function_response": {
            "id": None,
            "name": "test_tool",
            "response": {
                "error": "HomeAssistantError",
                "error_text": "Test tool exception",
            },
        },
        "inline_data": None,
        "text": None,
        "thought": None,
        "video_metadata": None,
    }
    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
            id="mock-tool-call",
            tool_name="test_tool",
            tool_args={"param1": 1},
        ),
        llm.LLMContext(
            platform="google_generative_ai_conversation",
            context=context,
            user_prompt="Please call the test function",
            language="en",
            assistant="conversation",
            device_id="test_device",
        ),
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_error_handling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that client errors are caught."""
    with patch("google.genai.chats.AsyncChats.create") as mock_create:
        mock_chat = AsyncMock()
        mock_create.return_value.send_message = mock_chat
        mock_chat.side_effect = CLIENT_ERROR_500
        result = await conversation.async_converse(
            hass,
            "hello",
            None,
            Context(),
            agent_id="conversation.google_generative_ai_conversation",
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        "Sorry, I had a problem talking to Google Generative AI: 500 internal-error. {'message': 'Internal Server Error', 'status': 'internal-error'}"
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_blocked_response(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test blocked response."""
    with patch("google.genai.chats.AsyncChats.create") as mock_create:
        mock_chat = AsyncMock()
        mock_create.return_value.send_message = mock_chat
        chat_response = Mock(prompt_feedback=Mock(block_reason_message="SAFETY"))
        mock_chat.return_value = chat_response

        result = await conversation.async_converse(
            hass,
            "hello",
            None,
            Context(),
            agent_id="conversation.google_generative_ai_conversation",
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        "The message got blocked due to content violations, reason: SAFETY"
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_empty_response(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test empty response."""
    with patch("google.genai.chats.AsyncChats.create") as mock_create:
        mock_chat = AsyncMock()
        mock_create.return_value.send_message = mock_chat
        chat_response = Mock(prompt_feedback=None)
        mock_chat.return_value = chat_response
        chat_response.candidates = [Mock(content=Mock(parts=[]))]
        result = await conversation.async_converse(
            hass,
            "hello",
            None,
            Context(),
            agent_id="conversation.google_generative_ai_conversation",
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        ERROR_GETTING_RESPONSE
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_none_response(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test empty response."""
    with patch("google.genai.chats.AsyncChats.create") as mock_create:
        mock_chat = AsyncMock()
        mock_create.return_value.send_message = mock_chat
        chat_response = Mock(prompt_feedback=None)
        mock_chat.return_value = chat_response
        chat_response.candidates = None
        result = await conversation.async_converse(
            hass,
            "hello",
            None,
            Context(),
            agent_id="conversation.google_generative_ai_conversation",
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        ERROR_GETTING_RESPONSE
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_converse_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test handling ChatLog raising ConverseError."""
    with patch("google.genai.models.AsyncModels.get"):
        hass.config_entries.async_update_entry(
            mock_config_entry,
            options={**mock_config_entry.options, CONF_LLM_HASS_API: "invalid_llm_api"},
        )
        await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass,
        "hello",
        None,
        Context(),
        agent_id="conversation.google_generative_ai_conversation",
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        "Error preparing LLM API"
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_conversation_agent(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test GoogleGenerativeAIAgent."""
    agent = conversation.get_agent_manager(hass).async_get_agent(
        mock_config_entry.entry_id
    )
    assert agent.supported_languages == "*"


async def test_escape_decode() -> None:
    """Test _escape_decode."""
    assert _escape_decode(
        {
            "param1": ["test_value", "param1\\'s value"],
            "param2": "param2\\'s value",
            "param3": {"param31": "Cheminée", "param32": "Chemin\\303\\251e"},
        }
    ) == {
        "param1": ["test_value", "param1's value"],
        "param2": "param2's value",
        "param3": {"param31": "Cheminée", "param32": "Cheminée"},
    }


@pytest.mark.parametrize(
    ("openapi", "genai_schema"),
    [
        (
            {"type": "string", "enum": ["a", "b", "c"]},
            {"type": "STRING", "enum": ["a", "b", "c"]},
        ),
        (
            {"type": "string", "default": "default"},
            {"type": "STRING"},
        ),
        (
            {"type": "string", "pattern": "default"},
            {"type": "STRING"},
        ),
        (
            {"type": "string", "maxLength": 10},
            {"type": "STRING"},
        ),
        (
            {"type": "string", "minLength": 10},
            {"type": "STRING"},
        ),
        (
            {"type": "string", "title": "title"},
            {"type": "STRING"},
        ),
        (
            {"type": "string", "format": "enum", "enum": ["a", "b", "c"]},
            {"type": "STRING", "format": "enum", "enum": ["a", "b", "c"]},
        ),
        (
            {"type": "string", "format": "date-time"},
            {"type": "STRING", "format": "date-time"},
        ),
        (
            {"type": "string", "format": "byte"},
            {"type": "STRING"},
        ),
        (
            {"type": "number", "format": "float"},
            {"type": "NUMBER", "format": "float"},
        ),
        (
            {"type": "number", "format": "double"},
            {"type": "NUMBER", "format": "double"},
        ),
        (
            {"type": "number", "format": "hex"},
            {"type": "NUMBER"},
        ),
        (
            {"type": "number", "minimum": 1},
            {"type": "NUMBER"},
        ),
        (
            {"type": "integer", "format": "int32"},
            {"type": "INTEGER", "format": "int32"},
        ),
        (
            {"type": "integer", "format": "int64"},
            {"type": "INTEGER", "format": "int64"},
        ),
        (
            {"type": "integer", "format": "int8"},
            {"type": "INTEGER"},
        ),
        (
            {"type": "integer", "enum": [1, 2, 3]},
            {"type": "STRING", "enum": ["1", "2", "3"]},
        ),
        (
            {"anyOf": [{"type": "integer"}, {"type": "number"}]},
            {},
        ),
        ({"type": "string", "format": "lower"}, {"type": "STRING"}),
        ({"type": "boolean", "format": "bool"}, {"type": "BOOLEAN"}),
        (
            {"type": "number", "format": "percent"},
            {"type": "NUMBER"},
        ),
        (
            {
                "type": "object",
                "properties": {"var": {"type": "string"}},
                "required": [],
            },
            {
                "type": "OBJECT",
                "properties": {"var": {"type": "STRING"}},
                "required": [],
            },
        ),
        (
            {"type": "object", "additionalProperties": True, "minProperties": 1},
            {
                "type": "OBJECT",
                "properties": {"json": {"type": "STRING"}},
                "required": [],
            },
        ),
        (
            {"type": "object", "additionalProperties": True, "maxProperties": 1},
            {
                "type": "OBJECT",
                "properties": {"json": {"type": "STRING"}},
                "required": [],
            },
        ),
        (
            {"type": "array", "items": {"type": "string"}},
            {"type": "ARRAY", "items": {"type": "STRING"}},
        ),
        (
            {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 2,
            },
            {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "min_items": 1,
                "max_items": 2,
            },
        ),
    ],
)
async def test_format_schema(openapi, genai_schema) -> None:
    """Test _format_schema."""
    assert _format_schema(openapi) == genai_schema


@pytest.mark.usefixtures("mock_init_component")
async def test_empty_content_in_chat_history(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Tests that in case of an empty entry in the chat history the google API will receive an injected space sign instead."""
    with (
        patch("google.genai.chats.AsyncChats.create") as mock_create,
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session) as chat_log,
    ):
        mock_chat = AsyncMock()
        mock_create.return_value.send_message = mock_chat

        # Chat preparation with two inputs, one being an empty string
        first_input = "First request"
        second_input = ""
        chat_log.async_add_user_content(UserContent(first_input))
        chat_log.async_add_user_content(UserContent(second_input))

        await conversation.async_converse(
            hass,
            "Second request",
            session.conversation_id,
            Context(),
            agent_id="conversation.google_generative_ai_conversation",
        )

        _, kwargs = mock_create.call_args
        actual_history = kwargs.get("history")

        assert actual_history[0].parts[0].text == first_input
        assert actual_history[1].parts[0].text == " "


@pytest.mark.usefixtures("mock_init_component")
async def test_history_always_user_first_turn(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the user is always first in the chat history."""
    with (
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session) as chat_log,
    ):
        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id="conversation.google_generative_ai_conversation",
                content="Garage door left open, do you want to close it?",
            )
        )

    with patch("google.genai.chats.AsyncChats.create") as mock_create:
        mock_chat = AsyncMock()
        mock_create.return_value.send_message = mock_chat
        chat_response = Mock(prompt_feedback=None)
        mock_chat.return_value = chat_response
        chat_response.candidates = [Mock(content=Mock(parts=[]))]

        await conversation.async_converse(
            hass,
            "hello",
            chat_log.conversation_id,
            Context(),
            agent_id="conversation.google_generative_ai_conversation",
        )

    _, kwargs = mock_create.call_args
    actual_history = kwargs.get("history")

    assert actual_history[0].parts[0].text == " "
    assert actual_history[0].role == "user"
    assert (
        actual_history[1].parts[0].text
        == "Garage door left open, do you want to close it?"
    )
    assert actual_history[1].role == "model"
