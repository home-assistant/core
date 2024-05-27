"""Tests for the Google Generative AI Conversation integration conversation platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from freezegun import freeze_time
from google.api_core.exceptions import GoogleAPICallError
import google.generativeai.types as genai_types
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.conversation import trace
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    intent,
    llm,
)

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
    "config_entry_options",
    [
        {},
        {CONF_LLM_HASS_API: llm.LLM_API_ASSIST},
    ],
)
async def test_default_prompt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    agent_id: str | None,
    config_entry_options: {},
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the default prompt works."""
    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)
    for i in range(3):
        area_registry.async_create(f"{i}Empty Area")

    if agent_id is None:
        agent_id = mock_config_entry.entry_id

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, **config_entry_options},
    )
    entities = []

    def create_entity(device: dr.DeviceEntry) -> None:
        """Create an entity for a device and track entity_id."""
        entity = entity_registry.async_get_or_create(
            "light",
            "test",
            device.id,
            device_id=device.id,
            original_name=str(device.name),
            suggested_object_id=str(device.name),
        )
        entity.write_unavailable_state(hass)
        entities.append(entity.entity_id)

    create_entity(
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={("test", "1234")},
            name="Test Device",
            manufacturer="Test Manufacturer",
            model="Test Model",
            suggested_area="Test Area",
        )
    )
    for i in range(3):
        create_entity(
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                connections={("test", f"{i}abcd")},
                name="Test Service",
                manufacturer="Test Manufacturer",
                model="Test Model",
                suggested_area="Test Area",
                entry_type=dr.DeviceEntryType.SERVICE,
            )
        )
    create_entity(
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={("test", "5678")},
            name="Test Device 2",
            manufacturer="Test Manufacturer 2",
            model="Device 2",
            suggested_area="Test Area 2",
        )
    )
    create_entity(
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={("test", "9876")},
            name="Test Device 3",
            manufacturer="Test Manufacturer 3",
            model="Test Model 3A",
            suggested_area="Test Area 2",
        )
    )
    create_entity(
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={("test", "qwer")},
            name="Test Device 4",
            suggested_area="Test Area 2",
        )
    )
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "9876-disabled")},
        name="Test Device 3",
        manufacturer="Test Manufacturer 3",
        model="Test Model 3A",
        suggested_area="Test Area 2",
    )
    device_registry.async_update_device(
        device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    create_entity(device)
    create_entity(
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={("test", "9876-no-name")},
            manufacturer="Test Manufacturer NoName",
            model="Test Model NoName",
            suggested_area="Test Area 2",
        )
    )
    create_entity(
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={("test", "9876-integer-values")},
            name=1,
            manufacturer=2,
            model=3,
            suggested_area="Test Area 2",
        )
    )

    # Set options for registered entities
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json_auto_id(
        {
            "type": "homeassistant/expose_entity",
            "assistants": ["conversation"],
            "entity_ids": entities,
            "should_expose": True,
        }
    )
    response = await ws_client.receive_json()
    assert response["success"]

    with (
        patch("google.generativeai.GenerativeModel") as mock_model,
        patch(
            "homeassistant.components.google_generative_ai_conversation.conversation.llm.AssistAPI.async_get_tools",
            return_value=[],
        ) as mock_get_tools,
    ):
        mock_chat = AsyncMock()
        mock_model.return_value.start_chat.return_value = mock_chat
        chat_response = MagicMock()
        mock_chat.send_message_async.return_value = chat_response
        mock_part = MagicMock()
        mock_part.function_call = None
        chat_response.parts = [mock_part]
        chat_response.text = "Hi there!"
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


async def test_chat_history(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the agent keeps track of the chat history."""
    with patch("google.generativeai.GenerativeModel") as mock_model:
        mock_chat = AsyncMock()
        mock_model.return_value.start_chat.return_value = mock_chat
        chat_response = MagicMock()
        mock_chat.send_message_async.return_value = chat_response
        mock_part = MagicMock()
        mock_part.function_call = None
        chat_response.parts = [mock_part]
        chat_response.text = "1st model response"
        mock_chat.history = [
            {"role": "user", "parts": "prompt"},
            {"role": "model", "parts": "Ok"},
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
        chat_response.text = "2nd model response"
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
    "homeassistant.components.google_generative_ai_conversation.conversation.llm.AssistAPI.async_get_tools"
)
async def test_function_call(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test that the default prompt works."""
    agent_id = mock_config_entry_with_assist.entry_id
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {
            vol.Optional("param1", description="Test parameters"): [
                vol.All(str, vol.Lower)
            ]
        }
    )

    mock_get_tools.return_value = [mock_tool]

    with patch("google.generativeai.GenerativeModel") as mock_model:
        mock_chat = AsyncMock()
        mock_model.return_value.start_chat.return_value = mock_chat
        chat_response = MagicMock()
        mock_chat.send_message_async.return_value = chat_response
        mock_part = MagicMock()
        mock_part.function_call.name = "test_tool"
        mock_part.function_call.args = {"param1": ["test_value"]}

        def tool_call(hass, tool_input):
            mock_part.function_call = False
            chat_response.text = "Hi there!"
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
            tool_args={"param1": ["test_value"]},
            platform="google_generative_ai_conversation",
            context=context,
            user_prompt="Please call the test function",
            language="en",
            assistant="conversation",
            device_id="test_device",
        ),
    )

    # Test conversating tracing
    traces = trace.async_get_traces()
    assert traces
    last_trace = traces[-1].as_dict()
    trace_events = last_trace.get("events", [])
    assert [event["event_type"] for event in trace_events] == [
        trace.ConversationTraceEventType.ASYNC_PROCESS,
        trace.ConversationTraceEventType.AGENT_DETAIL,
        trace.ConversationTraceEventType.LLM_TOOL_CALL,
    ]
    # AGENT_DETAIL event contains the raw prompt passed to the model
    detail_event = trace_events[1]
    assert "Answer in plain text" in detail_event["data"]["messages"][0]["parts"]


@patch(
    "homeassistant.components.google_generative_ai_conversation.conversation.llm.AssistAPI.async_get_tools"
)
async def test_function_exception(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test that the default prompt works."""
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
        mock_part.function_call.name = "test_tool"
        mock_part.function_call.args = {"param1": 1}

        def tool_call(hass, tool_input):
            mock_part.function_call = False
            chat_response.text = "Hi there!"
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
            platform="google_generative_ai_conversation",
            context=context,
            user_prompt="Please call the test function",
            language="en",
            assistant="conversation",
            device_id="test_device",
        ),
    )


async def test_error_handling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test that client errors are caught."""
    with patch("google.generativeai.GenerativeModel") as mock_model:
        mock_chat = AsyncMock()
        mock_model.return_value.start_chat.return_value = mock_chat
        mock_chat.send_message_async.side_effect = GoogleAPICallError("some error")
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        "Sorry, I had a problem talking to Google Generative AI: None some error"
    )


async def test_blocked_response(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
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


async def test_empty_response(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
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


async def test_invalid_llm_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
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
    with (
        patch(
            "google.generativeai.get_model",
        ),
        patch("google.generativeai.GenerativeModel"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
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
    """Test GoogleGenerativeAIAgent."""
    agent = conversation.get_agent_manager(hass).async_get_agent(
        mock_config_entry.entry_id
    )
    assert agent.supported_languages == "*"
