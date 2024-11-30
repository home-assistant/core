"""Tests for the Google Generative AI Conversation integration conversation platform."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun import freeze_time
from google.ai.generativelanguage_v1beta.types.content import FunctionCall
from google.api_core.exceptions import GoogleAPIError
import google.generativeai.types as genai_types
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.conversation import trace
from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_CHAT_MODEL,
)
from homeassistant.components.google_generative_ai_conversation.conversation import (
    _escape_decode,
    _format_schema,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent, llm

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
def freeze_the_time():
    """Freeze the time."""
    with freeze_time("2024-05-24 12:00:00", tz_offset=0):
        yield


@pytest.mark.parametrize(
    "agent_id", [None, "conversation.google_generative_ai_conversation"]
)
@pytest.mark.parametrize(
    ("config_entry_options", "expected_features"),
    [
        ({}, 0),
        (
            {CONF_LLM_HASS_API: llm.LLM_API_ASSIST},
            conversation.ConversationEntityFeature.CONTROL,
        ),
    ],
)
@pytest.mark.usefixtures("mock_init_component")
async def test_default_prompt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    agent_id: str | None,
    config_entry_options: {},
    expected_features: conversation.ConversationEntityFeature,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the default prompt works."""
    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)

    if agent_id is None:
        agent_id = mock_config_entry.entry_id

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, **config_entry_options},
    )

    with (
        patch("google.generativeai.GenerativeModel") as mock_model,
        patch(
            "homeassistant.components.google_generative_ai_conversation.conversation.llm.AssistAPI._async_get_tools",
            return_value=[],
        ) as mock_get_tools,
        patch(
            "homeassistant.components.google_generative_ai_conversation.conversation.llm.AssistAPI._async_get_api_prompt",
            return_value="<api_prompt>",
        ),
    ):
        mock_chat = AsyncMock()
        mock_model.return_value.start_chat.return_value = mock_chat
        chat_response = MagicMock()
        mock_chat.send_message_async.return_value = chat_response
        mock_part = MagicMock()
        mock_part.function_call = None
        mock_part.text = "Hi there!\n"
        chat_response.parts = [mock_part]
        result = await conversation.async_converse(
            hass,
            "hello",
            None,
            Context(),
            agent_id=agent_id,
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.as_dict()["speech"]["plain"]["speech"] == "Hi there!"
    assert [tuple(mock_call) for mock_call in mock_model.mock_calls] == snapshot
    assert mock_get_tools.called == (CONF_LLM_HASS_API in config_entry_options)

    state = hass.states.get("conversation.google_generative_ai_conversation")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == expected_features


@pytest.mark.parametrize(
    ("model_name", "supports_system_instruction"),
    [("models/gemini-1.5-pro", True), ("models/gemini-1.0-pro", False)],
)
@pytest.mark.usefixtures("mock_init_component")
async def test_chat_history(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    model_name: str,
    supports_system_instruction: bool,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the agent keeps track of the chat history."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_CHAT_MODEL: model_name}
    )
    with patch("google.generativeai.GenerativeModel") as mock_model:
        mock_chat = AsyncMock()
        mock_model.return_value.start_chat.return_value = mock_chat
        chat_response = MagicMock()
        mock_chat.send_message_async.return_value = chat_response
        mock_part = MagicMock()
        mock_part.function_call = None
        mock_part.text = "1st model response"
        chat_response.parts = [mock_part]
        if supports_system_instruction:
            mock_chat.history = []
        else:
            mock_chat.history = [
                {"role": "user", "parts": "prompt"},
                {"role": "model", "parts": "Ok"},
            ]
        mock_chat.history += [
            {"role": "user", "parts": "1st user request"},
            {"role": "model", "parts": "1st model response"},
        ]
        result = await conversation.async_converse(
            hass,
            "1st user request",
            None,
            Context(),
            agent_id=mock_config_entry.entry_id,
        )
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
        assert (
            result.response.as_dict()["speech"]["plain"]["speech"]
            == "1st model response"
        )
        mock_part.text = "2nd model response"
        chat_response.parts = [mock_part]
        result = await conversation.async_converse(
            hass,
            "2nd user request",
            result.conversation_id,
            Context(),
            agent_id=mock_config_entry.entry_id,
        )
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
        assert (
            result.response.as_dict()["speech"]["plain"]["speech"]
            == "2nd model response"
        )

    assert [tuple(mock_call) for mock_call in mock_model.mock_calls] == snapshot


@patch(
    "homeassistant.components.google_generative_ai_conversation.conversation.llm.AssistAPI._async_get_tools"
)
@pytest.mark.usefixtures("mock_init_component")
async def test_function_call(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test function calling."""
    agent_id = mock_config_entry_with_assist.entry_id
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

    with patch("google.generativeai.GenerativeModel") as mock_model:
        mock_chat = AsyncMock()
        mock_model.return_value.start_chat.return_value = mock_chat
        chat_response = MagicMock()
        mock_chat.send_message_async.return_value = chat_response
        mock_part = MagicMock()
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
        chat_response.parts = [mock_part]
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
    mock_tool_call = mock_chat.send_message_async.mock_calls[1][1][0]
    mock_tool_call = type(mock_tool_call).to_dict(mock_tool_call)
    assert mock_tool_call == {
        "parts": [
            {
                "function_response": {
                    "name": "test_tool",
                    "response": {
                        "result": "Test response",
                    },
                },
            },
        ],
        "role": "",
    }

    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
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
    assert [tuple(mock_call) for mock_call in mock_model.mock_calls] == snapshot

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
    assert "Answer in plain text" in detail_event["data"]["prompt"]
    assert [t.name for t in detail_event["data"]["tools"]] == ["test_tool"]


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
    agent_id = mock_config_entry_with_assist.entry_id
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema({})

    mock_get_tools.return_value = [mock_tool]

    with patch("google.generativeai.GenerativeModel") as mock_model:
        mock_chat = AsyncMock()
        mock_model.return_value.start_chat.return_value = mock_chat
        chat_response = MagicMock()
        mock_chat.send_message_async.return_value = chat_response
        mock_part = MagicMock()
        mock_part.function_call = FunctionCall(name="test_tool", args={})

        def tool_call(
            hass: HomeAssistant, tool_input: llm.ToolInput, tool_context: llm.LLMContext
        ) -> dict[str, Any]:
            mock_part.function_call = None
            mock_part.text = "Hi there!"
            return {"result": "Test response"}

        mock_tool.async_call.side_effect = tool_call
        chat_response.parts = [mock_part]
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
    mock_tool_call = mock_chat.send_message_async.mock_calls[1][1][0]
    mock_tool_call = type(mock_tool_call).to_dict(mock_tool_call)
    assert mock_tool_call == {
        "parts": [
            {
                "function_response": {
                    "name": "test_tool",
                    "response": {
                        "result": "Test response",
                    },
                },
            },
        ],
        "role": "",
    }

    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
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
    assert [tuple(mock_call) for mock_call in mock_model.mock_calls] == snapshot


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
    agent_id = mock_config_entry_with_assist.entry_id
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

    with patch("google.generativeai.GenerativeModel") as mock_model:
        mock_chat = AsyncMock()
        mock_model.return_value.start_chat.return_value = mock_chat
        chat_response = MagicMock()
        mock_chat.send_message_async.return_value = chat_response
        mock_part = MagicMock()
        mock_part.function_call = FunctionCall(name="test_tool", args={"param1": 1})

        def tool_call(
            hass: HomeAssistant, tool_input: llm.ToolInput, tool_context: llm.LLMContext
        ) -> dict[str, Any]:
            mock_part.function_call = None
            mock_part.text = "Hi there!"
            raise HomeAssistantError("Test tool exception")

        mock_tool.async_call.side_effect = tool_call
        chat_response.parts = [mock_part]
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
    mock_tool_call = mock_chat.send_message_async.mock_calls[1][1][0]
    mock_tool_call = type(mock_tool_call).to_dict(mock_tool_call)
    assert mock_tool_call == {
        "parts": [
            {
                "function_response": {
                    "name": "test_tool",
                    "response": {
                        "error": "HomeAssistantError",
                        "error_text": "Test tool exception",
                    },
                },
            },
        ],
        "role": "",
    }
    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
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
    with patch("google.generativeai.GenerativeModel") as mock_model:
        mock_chat = AsyncMock()
        mock_model.return_value.start_chat.return_value = mock_chat
        mock_chat.send_message_async.side_effect = GoogleAPIError("some error")
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        "Sorry, I had a problem talking to Google Generative AI: some error"
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_blocked_response(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test blocked response."""
    with patch("google.generativeai.GenerativeModel") as mock_model:
        mock_chat = AsyncMock()
        mock_model.return_value.start_chat.return_value = mock_chat
        mock_chat.send_message_async.side_effect = genai_types.StopCandidateException(
            "finish_reason: SAFETY\n"
        )
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        "The message got blocked by your safety settings"
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_empty_response(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test empty response."""
    with patch("google.generativeai.GenerativeModel") as mock_model:
        mock_chat = AsyncMock()
        mock_model.return_value.start_chat.return_value = mock_chat
        chat_response = MagicMock()
        mock_chat.send_message_async.return_value = chat_response
        chat_response.parts = []
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        "Sorry, I had a problem getting a response from Google Generative AI."
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_invalid_llm_api(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test handling of invalid llm api."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, CONF_LLM_HASS_API: "invalid_llm_api"},
    )

    result = await conversation.async_converse(
        hass,
        "hello",
        None,
        Context(),
        agent_id=mock_config_entry.entry_id,
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        "Error preparing LLM API: API invalid_llm_api not found"
    )


async def test_template_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that template error handling works."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            "prompt": "talk like a {% if True %}smarthome{% else %}pirate please.",
        },
    )
    with patch("google.generativeai.GenerativeModel"):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result


async def test_template_variables(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that template variables work."""
    context = Context(user_id="12345")
    mock_user = MagicMock()
    mock_user.id = "12345"
    mock_user.name = "Test User"

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            "prompt": (
                "The user name is {{ user_name }}. "
                "The user id is {{ llm_context.context.user_id }}."
            ),
        },
    )
    with (
        patch("google.generativeai.GenerativeModel") as mock_model,
        patch("homeassistant.auth.AuthManager.async_get_user", return_value=mock_user),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        mock_chat = AsyncMock()
        mock_model.return_value.start_chat.return_value = mock_chat
        chat_response = MagicMock()
        mock_chat.send_message_async.return_value = chat_response
        mock_part = MagicMock()
        mock_part.text = "Model response"
        chat_response.parts = [mock_part]
        result = await conversation.async_converse(
            hass, "hello", None, context, agent_id=mock_config_entry.entry_id
        )

    assert (
        result.response.response_type == intent.IntentResponseType.ACTION_DONE
    ), result
    assert (
        "The user name is Test User."
        in mock_model.mock_calls[0][2]["system_instruction"]
    )
    assert "The user id is 12345." in mock_model.mock_calls[0][2]["system_instruction"]


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
    ("openapi", "protobuf"),
    [
        (
            {"type": "string", "enum": ["a", "b", "c"]},
            {"type_": "STRING", "enum": ["a", "b", "c"]},
        ),
        (
            {"type": "integer", "enum": [1, 2, 3]},
            {"type_": "STRING", "enum": ["1", "2", "3"]},
        ),
        ({"anyOf": [{"type": "integer"}, {"type": "number"}]}, {"type_": "INTEGER"}),
        (
            {
                "anyOf": [
                    {"anyOf": [{"type": "integer"}, {"type": "number"}]},
                    {"anyOf": [{"type": "integer"}, {"type": "number"}]},
                ]
            },
            {"type_": "INTEGER"},
        ),
        ({"type": "string", "format": "lower"}, {"type_": "STRING"}),
        ({"type": "boolean", "format": "bool"}, {"type_": "BOOLEAN"}),
        (
            {"type": "number", "format": "percent"},
            {"type_": "NUMBER", "format_": "percent"},
        ),
        (
            {
                "type": "object",
                "properties": {"var": {"type": "string"}},
                "required": [],
            },
            {
                "type_": "OBJECT",
                "properties": {"var": {"type_": "STRING"}},
                "required": [],
            },
        ),
        (
            {"type": "object", "additionalProperties": True},
            {
                "type_": "OBJECT",
                "properties": {"json": {"type_": "STRING"}},
                "required": [],
            },
        ),
        (
            {"type": "array", "items": {"type": "string"}},
            {"type_": "ARRAY", "items": {"type_": "STRING"}},
        ),
    ],
)
async def test_format_schema(openapi, protobuf) -> None:
    """Test _format_schema."""
    assert _format_schema(openapi) == protobuf
