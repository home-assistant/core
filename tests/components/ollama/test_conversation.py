"""Tests for the Ollama integration."""

from unittest.mock import AsyncMock, Mock, patch
import logging

from ollama import Message, ResponseError
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import conversation, ollama
from homeassistant.components.conversation import trace
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.const import ATTR_FRIENDLY_NAME, MATCH_ALL
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

_LOGGER = logging.getLogger(__name__)

@pytest.mark.parametrize("agent_id", [None, "conversation.mock_title"])
async def test_chat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    agent_id: str,
) -> None:
    """Test that the chat function is called with the appropriate arguments."""

    if agent_id is None:
        agent_id = mock_config_entry.entry_id

    # Create some areas, devices, and entities
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")
    area_bedroom = area_registry.async_get_or_create("bedroom_id")
    area_bedroom = area_registry.async_update(area_bedroom.id, name="bedroom")
    area_office = area_registry.async_get_or_create("office_id")
    area_office = area_registry.async_update(area_office.id, name="office")

    entry = MockConfigEntry()
    entry.add_to_hass(hass)
    kitchen_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("demo", "id-1234")},
    )
    device_registry.async_update_device(kitchen_device.id, area_id=area_kitchen.id)

    kitchen_light = entity_registry.async_get_or_create("light", "demo", "1234")
    kitchen_light = entity_registry.async_update_entity(
        kitchen_light.entity_id, device_id=kitchen_device.id
    )
    hass.states.async_set(
        kitchen_light.entity_id, "on", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )

    bedroom_light = entity_registry.async_get_or_create("light", "demo", "5678")
    bedroom_light = entity_registry.async_update_entity(
        bedroom_light.entity_id, area_id=area_bedroom.id
    )
    hass.states.async_set(
        bedroom_light.entity_id, "on", attributes={ATTR_FRIENDLY_NAME: "bedroom light"}
    )

    # Hide the office light
    office_light = entity_registry.async_get_or_create("light", "demo", "ABCD")
    office_light = entity_registry.async_update_entity(
        office_light.entity_id, area_id=area_office.id
    )
    hass.states.async_set(
        office_light.entity_id, "on", attributes={ATTR_FRIENDLY_NAME: "office light"}
    )
    async_expose_entity(hass, conversation.DOMAIN, office_light.entity_id, False)

    with patch(
        "ollama.AsyncClient.chat",
        return_value={"message": {"role": "assistant", "content": "test response"}},
    ) as mock_chat:
        result = await conversation.async_converse(
            hass,
            "test message",
            None,
            Context(),
            agent_id=agent_id,
        )

        assert mock_chat.call_count == 1
        args = mock_chat.call_args.kwargs
        prompt = args["messages"][0]["content"]

        assert args["model"] == "test model"
        assert args["messages"] == [
            Message({"role": "system", "content": prompt}),
            Message({"role": "user", "content": "test message"}),
        ]

        # Verify only exposed devices/areas are in prompt
        assert "kitchen light" in prompt
        assert "bedroom light" in prompt
        assert "office light" not in prompt
        assert "office" not in prompt

        assert (
            result.response.response_type == intent.IntentResponseType.ACTION_DONE
        ), result
        assert result.response.speech["plain"]["speech"] == "test response"

    # Test Conversation tracing
    traces = trace.async_get_traces()
    assert traces
    last_trace = traces[-1].as_dict()
    trace_events = last_trace.get("events", [])
    assert [event["event_type"] for event in trace_events] == [
        trace.ConversationTraceEventType.ASYNC_PROCESS,
        trace.ConversationTraceEventType.AGENT_DETAIL,
    ]
    # AGENT_DETAIL event contains the raw prompt passed to the model
    detail_event = trace_events[1]
    assert "The current time is" in detail_event["data"]["messages"][0]["content"]

async def test_template_variables(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that template variables work."""
    context = Context(user_id="12345")
    mock_user = Mock()
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
        patch("ollama.AsyncClient.list"),
        patch(
            "ollama.AsyncClient.chat",
            return_value={"message": {"role": "assistant", "content": "test response"}},
        ) as mock_chat,
        patch("homeassistant.auth.AuthManager.async_get_user", return_value=mock_user),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        result = await conversation.async_converse(
            hass, "hello", None, context, agent_id=mock_config_entry.entry_id
        )

    assert (
        result.response.response_type == intent.IntentResponseType.ACTION_DONE
    ), result

    args = mock_chat.call_args.kwargs
    prompt = args["messages"][0]["content"]

    assert "The user name is Test User." in prompt
    assert "The user id is 12345." in prompt


@patch("homeassistant.components.ollama.conversation.llm.AssistAPI._async_get_tools")
async def test_function_call(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test function call from the assistant."""
    agent_id = mock_config_entry_with_assist.entry_id
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )
    mock_tool.async_call.return_value = "Test response"

    mock_get_tools.return_value = [mock_tool]

    def completion_result(*args, messages, tools, **kwargs):
        _LOGGER.debug("tools=%s", tools)
        for message in messages:
            if message["role"] == "tool":
                return {
                    "message": {
                        "role": "assistant",
                        "content": "I have successfully called the function",
                    }
                }
        assert tools
        return {
            "message": {
                "role": "assistant",
                "content": "Calling tool",
                "tool_calls": [{
                    "function": {
                        "name": "test_tool",
                        "arguments": '{"param1": "test_value"}'
                    }
                }]
            }
        }

    with patch(
        "ollama.AsyncClient.chat",
        side_effect=completion_result,
    ) as mock_chat:
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
        )

    assert mock_chat.call_count == 2
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert (
        result.response.speech["plain"]["speech"]
        == "I have successfully called the function"
    )
    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
            tool_name="test_tool",
            tool_args={"param1": "test_value"},
        ),
        llm.LLMContext(
            platform="ollama",
            context=context,
            user_prompt="Please call the test function",
            language="en",
            assistant="conversation",
            device_id=None,
        ),
    )

    # Test Conversation tracing
    traces = trace.async_get_traces()
    assert traces
    last_trace = traces[-1].as_dict()
    trace_events = last_trace.get("events", [])
    assert [event["event_type"] for event in trace_events] == [
        trace.ConversationTraceEventType.ASYNC_PROCESS,
        trace.ConversationTraceEventType.AGENT_DETAIL,
        trace.ConversationTraceEventType.LLM_TOOL_CALL,
    ]


@patch("homeassistant.components.ollama.conversation.llm.AssistAPI._async_get_tools")
async def test_malformed_function_args(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test getting function args for an unknown function."""
    agent_id = mock_config_entry_with_assist.entry_id
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )
    mock_tool.async_call.return_value = "Test response"

    mock_get_tools.return_value = [mock_tool]

    def completion_result(*args, messages, **kwargs):
        for message in messages:
            if message["content"].startswith("TOOL_ARGS"):
                return {
                    "message": {
                        "role": "assistant",
                        "content": "I was not able to call the function",
                    }
                }

        return {
            "message": {
                "role": "assistant",
                "content": "TOOL_ARGS unknown_tool",
            }
        }

    with patch(
        "ollama.AsyncClient.chat",
        side_effect=completion_result,
    ) as mock_chat:
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
        )

    assert mock_tool.async_call.call_count == 0
    assert mock_chat.call_count == 2
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert (
        result.response.speech["plain"]["speech"]
        == "I was not able to call the function"
    )


@patch("homeassistant.components.ollama.conversation.llm.AssistAPI._async_get_tools")
async def test_malformed_function_call(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test function call that was unrecognized."""
    agent_id = mock_config_entry_with_assist.entry_id
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )
    mock_tool.async_call.return_value = "Test response"

    mock_get_tools.return_value = [mock_tool]

    def completion_result(*args, messages, **kwargs):
        for message in messages:
            if message["content"].startswith("TOOL_CALL"):
                return {
                    "message": {
                        "role": "assistant",
                        "content": "I was not able to call the function",
                    }
                }

        return {
            "message": {
                "role": "assistant",
                "content": 'TOOL_CALL name="test_tool", param1="test_value"',
            }
        }

    with patch(
        "ollama.AsyncClient.chat",
        side_effect=completion_result,
    ) as mock_chat:
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
        )

    assert mock_tool.async_call.call_count == 0
    assert mock_chat.call_count == 2
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert (
        result.response.speech["plain"]["speech"]
        == "I was not able to call the function"
    )


@patch("homeassistant.components.ollama.conversation.llm.AssistAPI._async_get_tools")
async def test_function_exception(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test function call with exception."""
    agent_id = mock_config_entry_with_assist.entry_id
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )
    mock_tool.async_call.side_effect = HomeAssistantError("Test tool exception")

    mock_get_tools.return_value = [mock_tool]

    def completion_result(*args, messages, **kwargs):
        for message in messages:
            if message["content"].startswith("TOOL_CALL"):
                return {
                    "message": {
                        "role": "assistant",
                        "content": "There was an error calling the function",
                    }
                }

        return {
            "message": {
                "role": "assistant",
                "content": 'TOOL_CALL {"name": "test_tool", "parameters": {"param1": "test_value"}}',
            }
        }

    with patch(
        "ollama.AsyncClient.chat",
        side_effect=completion_result,
    ) as mock_chat:
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
        )

    assert mock_chat.call_count == 2
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert (
        result.response.speech["plain"]["speech"]
        == "There was an error calling the function"
    )
    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
            tool_name="test_tool",
            tool_args={"param1": "test_value"},
        ),
        llm.LLMContext(
            platform="ollama",
            context=context,
            user_prompt="Please call the test function",
            language="en",
            assistant="conversation",
            device_id=None,
        ),
    )


async def test_unknown_hass_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_init_component,
) -> None:
    """Test when we reference an API that no longer exists."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_LLM_HASS_API: "non-existing",
        },
    )

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
    )

    assert result == snapshot


async def test_message_history_trimming(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test that a single message history is trimmed according to the config."""
    response_idx = 0

    def response(*args, **kwargs) -> dict:
        nonlocal response_idx
        response_idx += 1
        return {"message": {"role": "assistant", "content": f"response {response_idx}"}}

    with patch(
        "ollama.AsyncClient.chat",
        side_effect=response,
    ) as mock_chat:
        # mock_init_component sets "max_history" to 2
        for i in range(5):
            result = await conversation.async_converse(
                hass,
                f"message {i+1}",
                conversation_id="1234",
                context=Context(),
                agent_id=mock_config_entry.entry_id,
            )
            assert (
                result.response.response_type == intent.IntentResponseType.ACTION_DONE
            ), result

        assert mock_chat.call_count == 5
        args = mock_chat.call_args_list
        prompt = args[0].kwargs["messages"][0]["content"]

        # system + user-1
        assert len(args[0].kwargs["messages"]) == 2
        assert args[0].kwargs["messages"][1]["content"] == "message 1"

        # Full history
        # system + user-1 + assistant-1 + user-2
        assert len(args[1].kwargs["messages"]) == 4
        assert args[1].kwargs["messages"][0]["role"] == "system"
        assert args[1].kwargs["messages"][0]["content"] == prompt
        assert args[1].kwargs["messages"][1]["role"] == "user"
        assert args[1].kwargs["messages"][1]["content"] == "message 1"
        assert args[1].kwargs["messages"][2]["role"] == "assistant"
        assert args[1].kwargs["messages"][2]["content"] == "response 1"
        assert args[1].kwargs["messages"][3]["role"] == "user"
        assert args[1].kwargs["messages"][3]["content"] == "message 2"

        # Full history
        # system + user-1 + assistant-1 + user-2 + assistant-2 + user-3
        assert len(args[2].kwargs["messages"]) == 6
        assert args[2].kwargs["messages"][0]["role"] == "system"
        assert args[2].kwargs["messages"][0]["content"] == prompt
        assert args[2].kwargs["messages"][1]["role"] == "user"
        assert args[2].kwargs["messages"][1]["content"] == "message 1"
        assert args[2].kwargs["messages"][2]["role"] == "assistant"
        assert args[2].kwargs["messages"][2]["content"] == "response 1"
        assert args[2].kwargs["messages"][3]["role"] == "user"
        assert args[2].kwargs["messages"][3]["content"] == "message 2"
        assert args[2].kwargs["messages"][4]["role"] == "assistant"
        assert args[2].kwargs["messages"][4]["content"] == "response 2"
        assert args[2].kwargs["messages"][5]["role"] == "user"
        assert args[2].kwargs["messages"][5]["content"] == "message 3"

        # Trimmed down to two user messages.
        # system + user-2 + assistant-2 + user-3 + assistant-3 + user-4
        assert len(args[3].kwargs["messages"]) == 6
        assert args[3].kwargs["messages"][0]["role"] == "system"
        assert args[3].kwargs["messages"][0]["content"] == prompt
        assert args[3].kwargs["messages"][1]["role"] == "user"
        assert args[3].kwargs["messages"][1]["content"] == "message 2"
        assert args[3].kwargs["messages"][2]["role"] == "assistant"
        assert args[3].kwargs["messages"][2]["content"] == "response 2"
        assert args[3].kwargs["messages"][3]["role"] == "user"
        assert args[3].kwargs["messages"][3]["content"] == "message 3"
        assert args[3].kwargs["messages"][4]["role"] == "assistant"
        assert args[3].kwargs["messages"][4]["content"] == "response 3"
        assert args[3].kwargs["messages"][5]["role"] == "user"
        assert args[3].kwargs["messages"][5]["content"] == "message 4"

        # Trimmed down to two user messages.
        # system + user-3 + assistant-3 + user-4 + assistant-4 + user-5
        assert len(args[3].kwargs["messages"]) == 6
        assert args[4].kwargs["messages"][0]["role"] == "system"
        assert args[4].kwargs["messages"][0]["content"] == prompt
        assert args[4].kwargs["messages"][1]["role"] == "user"
        assert args[4].kwargs["messages"][1]["content"] == "message 3"
        assert args[4].kwargs["messages"][2]["role"] == "assistant"
        assert args[4].kwargs["messages"][2]["content"] == "response 3"
        assert args[4].kwargs["messages"][3]["role"] == "user"
        assert args[4].kwargs["messages"][3]["content"] == "message 4"
        assert args[4].kwargs["messages"][4]["role"] == "assistant"
        assert args[4].kwargs["messages"][4]["content"] == "response 4"
        assert args[4].kwargs["messages"][5]["role"] == "user"
        assert args[4].kwargs["messages"][5]["content"] == "message 5"


async def test_message_history_pruning(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test that old message histories are pruned."""
    with patch(
        "ollama.AsyncClient.chat",
        return_value={"message": {"role": "assistant", "content": "test response"}},
    ):
        # Create 3 different message histories
        conversation_ids: list[str] = []
        for i in range(3):
            result = await conversation.async_converse(
                hass,
                f"message {i+1}",
                conversation_id=None,
                context=Context(),
                agent_id=mock_config_entry.entry_id,
            )
            assert (
                result.response.response_type == intent.IntentResponseType.ACTION_DONE
            ), result
            assert isinstance(result.conversation_id, str)
            conversation_ids.append(result.conversation_id)

        agent = conversation.get_agent_manager(hass).async_get_agent(
            mock_config_entry.entry_id
        )
        assert len(agent._history) == 3
        assert agent._history.keys() == set(conversation_ids)

        # Modify the timestamps of the first 2 histories so they will be pruned
        # on the next cycle.
        for conversation_id in conversation_ids[:2]:
            # Move back 2 hours
            agent._history[conversation_id].timestamp -= 2 * 60 * 60

        # Next cycle
        result = await conversation.async_converse(
            hass,
            "test message",
            conversation_id=None,
            context=Context(),
            agent_id=mock_config_entry.entry_id,
        )
        assert (
            result.response.response_type == intent.IntentResponseType.ACTION_DONE
        ), result

        # Only the most recent histories should remain
        assert len(agent._history) == 2
        assert conversation_ids[-1] in agent._history
        assert result.conversation_id in agent._history


async def test_message_history_unlimited(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test that message history is not trimmed when max_history = 0."""
    conversation_id = "1234"
    with (
        patch(
            "ollama.AsyncClient.chat",
            return_value={"message": {"role": "assistant", "content": "test response"}},
        ),
        patch.object(mock_config_entry, "options", {ollama.CONF_MAX_HISTORY: 0}),
    ):
        for i in range(100):
            result = await conversation.async_converse(
                hass,
                f"message {i+1}",
                conversation_id=conversation_id,
                context=Context(),
                agent_id=mock_config_entry.entry_id,
            )
            assert (
                result.response.response_type == intent.IntentResponseType.ACTION_DONE
            ), result

        agent = conversation.get_agent_manager(hass).async_get_agent(
            mock_config_entry.entry_id
        )

        assert len(agent._history) == 1
        assert conversation_id in agent._history
        assert agent._history[conversation_id].num_user_messages == 100


async def test_error_handling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test error handling during converse."""
    with patch(
        "ollama.AsyncClient.chat",
        new_callable=AsyncMock,
        side_effect=ResponseError("test error"),
    ):
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result


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
    with patch(
        "ollama.AsyncClient.list",
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
    """Test OllamaConversationEntity."""
    agent = conversation.get_agent_manager(hass).async_get_agent(
        mock_config_entry.entry_id
    )
    assert agent.supported_languages == MATCH_ALL
