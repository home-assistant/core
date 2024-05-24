"""Tests for the Ollama integration."""

from unittest.mock import AsyncMock, patch

from ollama import Message, ResponseError
import pytest

from homeassistant.components import conversation, ollama
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.const import ATTR_FRIENDLY_NAME, MATCH_ALL
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    intent,
)

from tests.common import MockConfigEntry


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
