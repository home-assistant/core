"""Tests for the Google Generative AI Conversation integration conversation platform."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from freezegun import freeze_time
from google.genai.types import FunctionCall
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.conversation import trace
from homeassistant.components.google_generative_ai_conversation.conversation import (
    _escape_decode,
    _format_schema,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent, llm

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
    mock_tool_call = mock_create.mock_calls[2][2]["message"]
    assert mock_tool_call.model_dump() == {
        "parts": [
            {
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
            },
        ],
        "role": None,
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
        trace.ConversationTraceEventType.AGENT_DETAIL,
        trace.ConversationTraceEventType.TOOL_CALL,
    ]
    # AGENT_DETAIL event contains the raw prompt passed to the model
    detail_event = trace_events[1]
    assert "Answer in plain text" in detail_event["data"]["messages"][0]["content"]
    assert [
        p["tool_name"] for p in detail_event["data"]["messages"][2]["tool_calls"]
    ] == ["test_tool"]


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
    mock_tool_call = mock_create.mock_calls[2][2]["message"]
    assert mock_tool_call.model_dump() == {
        "parts": [
            {
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
            },
        ],
        "role": None,
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
    mock_tool_call = mock_create.mock_calls[2][2]["message"]
    assert mock_tool_call.model_dump() == {
        "parts": [
            {
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
            },
        ],
        "role": None,
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
        "Sorry, I had a problem getting a response from Google Generative AI."
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
            {"type": "integer", "enum": [1, 2, 3]},
            {"type": "STRING", "enum": ["1", "2", "3"]},
        ),
        (
            {"anyOf": [{"type": "integer"}, {"type": "number"}]},
            {"any_of": [{"type": "INTEGER"}, {"type": "NUMBER"}]},
        ),
        (
            {
                "any_of": [
                    {"any_of": [{"type": "integer"}, {"type": "number"}]},
                    {"any_of": [{"type": "integer"}, {"type": "number"}]},
                ]
            },
            {
                "any_of": [
                    {"any_of": [{"type": "INTEGER"}, {"type": "NUMBER"}]},
                    {"any_of": [{"type": "INTEGER"}, {"type": "NUMBER"}]},
                ]
            },
        ),
        ({"type": "string", "format": "lower"}, {"format": "lower", "type": "STRING"}),
        ({"type": "boolean", "format": "bool"}, {"format": "bool", "type": "BOOLEAN"}),
        (
            {"type": "number", "format": "percent"},
            {"type": "NUMBER", "format": "percent"},
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
            {"type": "object", "additionalProperties": True},
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
    ],
)
async def test_format_schema(openapi, genai_schema) -> None:
    """Test _format_schema."""
    assert _format_schema(openapi) == genai_schema
