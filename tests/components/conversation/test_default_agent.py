"""Test for the default agent."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import (
    async_get_assistant_settings,
)
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import DOMAIN as HASS_DOMAIN, Context, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity,
    entity_registry as er,
    intent,
)
from homeassistant.setup import async_setup_component

from . import expose_entity

from tests.common import MockConfigEntry, async_mock_service


@pytest.fixture
async def init_components(hass):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})


@pytest.mark.parametrize(
    "er_kwargs",
    [
        {"hidden_by": er.RegistryEntryHider.USER},
        {"hidden_by": er.RegistryEntryHider.INTEGRATION},
        {"entity_category": entity.EntityCategory.CONFIG},
        {"entity_category": entity.EntityCategory.DIAGNOSTIC},
    ],
)
async def test_hidden_entities_skipped(
    hass: HomeAssistant, init_components, er_kwargs, entity_registry: er.EntityRegistry
) -> None:
    """Test we skip hidden entities."""

    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="Test light", **er_kwargs
    )
    hass.states.async_set("light.test_light", "off")
    calls = async_mock_service(hass, HASS_DOMAIN, "turn_on")
    result = await conversation.async_converse(
        hass, "turn on test light", None, Context(), None
    )

    assert len(calls) == 0
    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_INTENT_MATCH


async def test_exposed_domains(hass: HomeAssistant, init_components) -> None:
    """Test that we can't interact with entities that aren't exposed."""
    hass.states.async_set(
        "media_player.test", "off", attributes={ATTR_FRIENDLY_NAME: "Test Media Player"}
    )

    result = await conversation.async_converse(
        hass, "turn on test media player", None, Context(), None
    )

    # This is an intent match failure instead of a handle failure because the
    # media player domain is not exposed.
    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_INTENT_MATCH


async def test_exposed_areas(
    hass: HomeAssistant,
    init_components,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that only expose areas with an exposed entity/device."""
    area_kitchen = area_registry.async_get_or_create("kitchen")
    area_bedroom = area_registry.async_get_or_create("bedroom")

    entry = MockConfigEntry()
    entry.add_to_hass(hass)
    kitchen_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("demo", "id-1234")},
    )
    device_registry.async_update_device(kitchen_device.id, area_id=area_kitchen.id)

    kitchen_light = entity_registry.async_get_or_create("light", "demo", "1234")
    entity_registry.async_update_entity(
        kitchen_light.entity_id, device_id=kitchen_device.id
    )
    hass.states.async_set(
        kitchen_light.entity_id, "on", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )

    bedroom_light = entity_registry.async_get_or_create("light", "demo", "5678")
    entity_registry.async_update_entity(
        bedroom_light.entity_id, area_id=area_bedroom.id
    )
    hass.states.async_set(
        bedroom_light.entity_id, "on", attributes={ATTR_FRIENDLY_NAME: "bedroom light"}
    )

    # Hide the bedroom light
    expose_entity(hass, bedroom_light.entity_id, False)

    result = await conversation.async_converse(
        hass, "turn on lights in the kitchen", None, Context(), None
    )

    # All is well for the exposed kitchen light
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE

    # Bedroom is not exposed because it has no exposed entities
    result = await conversation.async_converse(
        hass, "turn on lights in the bedroom", None, Context(), None
    )

    # This should be an intent match failure because the area isn't in the slot list
    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_INTENT_MATCH


async def test_conversation_agent(
    hass: HomeAssistant,
    init_components,
) -> None:
    """Test DefaultAgent."""
    agent = await conversation._get_agent_manager(hass).async_get_agent(
        conversation.HOME_ASSISTANT_AGENT
    )
    with patch(
        "homeassistant.components.conversation.default_agent.get_domains_and_languages",
        return_value={"homeassistant": ["dwarvish", "elvish", "entish"]},
    ):
        assert agent.supported_languages == ["dwarvish", "elvish", "entish"]


async def test_expose_flag_automatically_set(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test DefaultAgent sets the expose flag on all entities automatically."""
    assert await async_setup_component(hass, "homeassistant", {})

    light = entity_registry.async_get_or_create("light", "demo", "1234")
    test = entity_registry.async_get_or_create("test", "demo", "1234")

    assert async_get_assistant_settings(hass, conversation.DOMAIN) == {}

    assert await async_setup_component(hass, "conversation", {})
    await hass.async_block_till_done()
    with patch("homeassistant.components.http.start_http_server_and_save_config"):
        await hass.async_start()

    # After setting up conversation, the expose flag should now be set on all entities
    assert async_get_assistant_settings(hass, conversation.DOMAIN) == {
        light.entity_id: {"should_expose": True},
        test.entity_id: {"should_expose": False},
    }

    # New entities will automatically have the expose flag set
    new_light = "light.demo_2345"
    hass.states.async_set(new_light, "test")
    await hass.async_block_till_done()
    assert async_get_assistant_settings(hass, conversation.DOMAIN) == {
        light.entity_id: {"should_expose": True},
        new_light: {"should_expose": True},
        test.entity_id: {"should_expose": False},
    }


async def test_unexposed_entities_skipped(
    hass: HomeAssistant,
    init_components,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that unexposed entities are skipped in exposed areas."""
    area_kitchen = area_registry.async_get_or_create("kitchen")

    # Both lights are in the kitchen
    exposed_light = entity_registry.async_get_or_create("light", "demo", "1234")
    entity_registry.async_update_entity(
        exposed_light.entity_id,
        area_id=area_kitchen.id,
    )
    hass.states.async_set(exposed_light.entity_id, "off")

    unexposed_light = entity_registry.async_get_or_create("light", "demo", "5678")
    entity_registry.async_update_entity(
        unexposed_light.entity_id,
        area_id=area_kitchen.id,
    )
    hass.states.async_set(unexposed_light.entity_id, "off")

    # On light is exposed, the other is not
    expose_entity(hass, exposed_light.entity_id, True)
    expose_entity(hass, unexposed_light.entity_id, False)

    # Only one light should be turned on
    calls = async_mock_service(hass, "light", "turn_on")
    result = await conversation.async_converse(
        hass, "turn on kitchen lights", None, Context(), None
    )

    assert len(calls) == 1
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE

    # Only one light should be returned
    hass.states.async_set(exposed_light.entity_id, "on")
    hass.states.async_set(unexposed_light.entity_id, "on")
    result = await conversation.async_converse(
        hass, "how many lights are on in the kitchen", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(result.response.matched_states) == 1
    assert result.response.matched_states[0].entity_id == exposed_light.entity_id


async def test_trigger_sentences(hass: HomeAssistant, init_components) -> None:
    """Test registering/unregistering/matching a few trigger sentences."""
    trigger_sentences = ["It's party time", "It is time to party"]
    trigger_response = "Cowabunga!"

    agent = await conversation._get_agent_manager(hass).async_get_agent(
        conversation.HOME_ASSISTANT_AGENT
    )
    assert isinstance(agent, conversation.DefaultAgent)

    callback = AsyncMock(return_value=trigger_response)
    unregister = agent.register_trigger(trigger_sentences, callback)

    result = await conversation.async_converse(hass, "Not the trigger", None, Context())
    assert result.response.response_type == intent.IntentResponseType.ERROR

    # Using different case and including punctuation
    test_sentences = ["it's party time!", "IT IS TIME TO PARTY."]
    for sentence in test_sentences:
        callback.reset_mock()
        result = await conversation.async_converse(hass, sentence, None, Context())
        assert callback.call_count == 1
        assert callback.call_args[0][0] == sentence
        assert (
            result.response.response_type == intent.IntentResponseType.ACTION_DONE
        ), sentence
        assert result.response.speech == {
            "plain": {"speech": trigger_response, "extra_data": None}
        }

    unregister()

    # Should produce errors now
    callback.reset_mock()
    for sentence in test_sentences:
        result = await conversation.async_converse(hass, sentence, None, Context())
        assert (
            result.response.response_type == intent.IntentResponseType.ERROR
        ), sentence

    assert len(callback.mock_calls) == 0


async def test_shopping_list_add_item(
    hass: HomeAssistant, init_components, sl_setup
) -> None:
    """Test adding an item to the shopping list through the default agent."""
    result = await conversation.async_converse(
        hass, "add apples to my shopping list", None, Context()
    )
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.speech == {
        "plain": {"speech": "Added apples", "extra_data": None}
    }


async def test_intent_context(
    hass: HomeAssistant, init_components, mock_device
) -> None:
    """Test if sending a device ID that's associated to an area adds area context to the intent."""

    with patch(
        "homeassistant.components.conversation.default_agent.recognize_all",
        wraps=conversation.default_agent.recognize_all,
    ) as mock_recognize:
        result = await conversation.async_converse(
            hass, "how many lights are on", None, Context(), device_id=mock_device.id
        )

        assert result.response.response_type == intent.IntentResponseType.QUERY_ANSWER
        assert mock_recognize.call_args.kwargs["intent_context"]
        assert mock_recognize.call_args.kwargs["intent_context"]["area"] == "kitchen"
