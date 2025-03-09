"""Test for the default agent."""

from collections import defaultdict
import os
import tempfile
from typing import Any
from unittest.mock import AsyncMock, patch

from hassil.recognize import Intent, IntentData, MatchEntity, RecognizeResult
import pytest
from syrupy import SnapshotAssertion
import yaml

from homeassistant.components import conversation, cover, media_player, weather
from homeassistant.components.conversation import default_agent
from homeassistant.components.conversation.const import DATA_DEFAULT_ENTITY
from homeassistant.components.conversation.default_agent import METADATA_CUSTOM_SENTENCE
from homeassistant.components.conversation.models import ConversationInput
from homeassistant.components.cover import SERVICE_OPEN_COVER
from homeassistant.components.homeassistant.exposed_entities import (
    async_get_assistant_settings,
)
from homeassistant.components.intent import (
    TimerEventType,
    TimerInfo,
    async_register_timer_handler,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    STATE_CLOSED,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    Context,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    intent,
)
from homeassistant.setup import async_setup_component

from . import expose_entity, expose_new

from tests.common import (
    MockConfigEntry,
    MockUser,
    async_mock_service,
    setup_test_component_platform,
)
from tests.components.light.common import MockLight


class OrderBeerIntentHandler(intent.IntentHandler):
    """Handle OrderBeer intent."""

    intent_type = "OrderBeer"

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Return speech response."""
        beer_style = intent_obj.slots["beer_style"]["value"]
        response = intent_obj.create_response()
        response.async_set_speech(f"You ordered a {beer_style}")
        return response


@pytest.fixture
async def init_components(hass: HomeAssistant) -> None:
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})


@pytest.mark.parametrize(
    "er_kwargs",
    [
        {"hidden_by": er.RegistryEntryHider.USER},
        {"hidden_by": er.RegistryEntryHider.INTEGRATION},
        {"entity_category": EntityCategory.CONFIG},
        {"entity_category": EntityCategory.DIAGNOSTIC},
    ],
)
@pytest.mark.usefixtures("init_components")
async def test_hidden_entities_skipped(
    hass: HomeAssistant, er_kwargs: dict[str, Any], entity_registry: er.EntityRegistry
) -> None:
    """Test we skip hidden entities."""

    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="Test light", **er_kwargs
    )
    hass.states.async_set("light.test_light", "off")
    calls = async_mock_service(hass, HOMEASSISTANT_DOMAIN, "turn_on")
    result = await conversation.async_converse(
        hass, "turn on test light", None, Context(), None
    )

    assert len(calls) == 0
    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS


@pytest.mark.usefixtures("init_components")
async def test_exposed_domains(hass: HomeAssistant) -> None:
    """Test that we can't interact with entities that aren't exposed."""
    hass.states.async_set(
        "lock.front_door", "off", attributes={ATTR_FRIENDLY_NAME: "Front Door"}
    )
    hass.states.async_set(
        "script.my_script", "off", attributes={ATTR_FRIENDLY_NAME: "My Script"}
    )

    # These are match failures instead of handle failures because the domains
    # aren't exposed by default.
    result = await conversation.async_converse(
        hass, "unlock front door", None, Context(), None
    )
    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS

    result = await conversation.async_converse(
        hass, "run my script", None, Context(), None
    )
    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS


@pytest.mark.usefixtures("init_components")
async def test_exposed_areas(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that all areas are exposed."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")
    area_bedroom = area_registry.async_get_or_create("bedroom_id")
    area_bedroom = area_registry.async_update(area_bedroom.id, name="bedroom")

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

    # Hide the bedroom light
    expose_entity(hass, bedroom_light.entity_id, False)

    result = await conversation.async_converse(
        hass, "turn on lights in the kitchen", None, Context(), None
    )

    # All is well for the exposed kitchen light
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.intent is not None
    assert result.response.intent.slots["area"]["value"] == area_kitchen.id
    assert result.response.intent.slots["area"]["text"] == area_kitchen.normalized_name

    # Bedroom has no exposed entities
    result = await conversation.async_converse(
        hass, "turn on lights in the bedroom", None, Context(), None
    )

    # This should be an error because the lights in that area are not exposed
    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS

    # But we can still ask questions about the bedroom, even with no exposed entities
    result = await conversation.async_converse(
        hass, "how many lights are on in the bedroom?", None, Context(), None
    )
    assert result.response.response_type == intent.IntentResponseType.QUERY_ANSWER


@pytest.mark.usefixtures("init_components")
async def test_conversation_agent(hass: HomeAssistant) -> None:
    """Test DefaultAgent."""
    agent = hass.data[DATA_DEFAULT_ENTITY]
    with patch(
        "homeassistant.components.conversation.default_agent.get_languages",
        return_value=["dwarvish", "elvish", "entish"],
    ):
        assert agent.supported_languages == ["dwarvish", "elvish", "entish"]

    state = hass.states.get(agent.entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert (
        state.attributes["supported_features"]
        == conversation.ConversationEntityFeature.CONTROL
    )


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
        "conversation.home_assistant": {"should_expose": False},
        light.entity_id: {"should_expose": True},
        test.entity_id: {"should_expose": False},
    }

    # New entities will automatically have the expose flag set
    new_light = "light.demo_2345"
    hass.states.async_set(new_light, "test")
    await hass.async_block_till_done()
    assert async_get_assistant_settings(hass, conversation.DOMAIN) == {
        "conversation.home_assistant": {"should_expose": False},
        light.entity_id: {"should_expose": True},
        new_light: {"should_expose": True},
        test.entity_id: {"should_expose": False},
    }


@pytest.mark.usefixtures("init_components")
async def test_unexposed_entities_skipped(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that unexposed entities are skipped in exposed areas."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")

    # Both lights are in the kitchen
    exposed_light = entity_registry.async_get_or_create("light", "demo", "1234")
    exposed_light = entity_registry.async_update_entity(
        exposed_light.entity_id,
        area_id=area_kitchen.id,
    )
    hass.states.async_set(exposed_light.entity_id, "off")

    unexposed_light = entity_registry.async_get_or_create("light", "demo", "5678")
    unexposed_light = entity_registry.async_update_entity(
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
    assert result.response.intent is not None
    assert result.response.intent.slots["area"]["value"] == area_kitchen.id
    assert result.response.intent.slots["area"]["text"] == area_kitchen.normalized_name

    # Only one light should be returned
    hass.states.async_set(exposed_light.entity_id, "on")
    hass.states.async_set(unexposed_light.entity_id, "on")
    result = await conversation.async_converse(
        hass, "how many lights are on in the kitchen", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(result.response.matched_states) == 1
    assert result.response.matched_states[0].entity_id == exposed_light.entity_id


@pytest.mark.usefixtures("init_components")
async def test_duplicated_names_resolved_with_device_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities deduplication with device ID context."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_bedroom = area_registry.async_get_or_create("bedroom_id")

    kitchen_light = entity_registry.async_get_or_create("light", "demo", "1234")
    bedroom_light = entity_registry.async_get_or_create("light", "demo", "5678")

    # Same name and alias
    for light in (kitchen_light, bedroom_light):
        light = entity_registry.async_update_entity(
            light.entity_id,
            name="top light",
            aliases={"overhead light"},
        )
        hass.states.async_set(
            light.entity_id,
            "off",
            attributes={ATTR_FRIENDLY_NAME: light.name},
        )
    # Different areas
    kitchen_light = entity_registry.async_update_entity(
        kitchen_light.entity_id,
        area_id=area_kitchen.id,
    )
    bedroom_light = entity_registry.async_update_entity(
        bedroom_light.entity_id,
        area_id=area_bedroom.id,
    )

    # Pipeline device in bedroom area
    entry = MockConfigEntry()
    entry.add_to_hass(hass)
    assist_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("demo", "id-1234")},
    )
    assist_device = device_registry.async_update_device(
        assist_device.id,
        area_id=area_bedroom.id,
    )

    # Check name and alias
    for name in ("top light", "overhead light"):
        # Only one light should be turned on
        calls = async_mock_service(hass, "light", "turn_on")
        result = await conversation.async_converse(
            hass, f"turn on {name}", None, Context(), device_id=assist_device.id
        )

        assert len(calls) == 1
        assert calls[0].data["entity_id"][0] == bedroom_light.entity_id

        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
        assert result.response.intent is not None
        assert result.response.intent.slots.get("name", {}).get("value") == name
        assert result.response.intent.slots.get("name", {}).get("text") == name


@pytest.mark.usefixtures("init_components")
async def test_trigger_sentences(hass: HomeAssistant) -> None:
    """Test registering/unregistering/matching a few trigger sentences."""
    trigger_sentences = ["It's party time", "It is time to party"]
    trigger_response = "Cowabunga!"

    agent = hass.data[DATA_DEFAULT_ENTITY]
    assert isinstance(agent, default_agent.DefaultAgent)

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
        assert callback.call_args[0][0].text == sentence
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE, (
            sentence
        )
        assert result.response.speech == {
            "plain": {"speech": trigger_response, "extra_data": None}
        }

    unregister()

    # Should produce errors now
    callback.reset_mock()
    for sentence in test_sentences:
        result = await conversation.async_converse(hass, sentence, None, Context())
        assert result.response.response_type == intent.IntentResponseType.ERROR, (
            sentence
        )

    assert len(callback.mock_calls) == 0


@pytest.mark.parametrize(
    ("language", "expected"),
    [("en", "English done"), ("de", "German done"), ("not_translated", "Done")],
)
@pytest.mark.usefixtures("init_components")
async def test_trigger_sentence_response_translation(
    hass: HomeAssistant, language: str, expected: str
) -> None:
    """Test translation of default response 'done'."""
    hass.config.language = language

    agent = hass.data[DATA_DEFAULT_ENTITY]
    assert isinstance(agent, default_agent.DefaultAgent)

    translations = {
        "en": {"component.conversation.conversation.agent.done": "English done"},
        "de": {"component.conversation.conversation.agent.done": "German done"},
        "not_translated": {},
    }

    with patch(
        "homeassistant.components.conversation.default_agent.translation.async_get_translations",
        return_value=translations.get(language),
    ):
        unregister = agent.register_trigger(
            ["test sentence"], AsyncMock(return_value=None)
        )
        result = await conversation.async_converse(
            hass, "test sentence", None, Context()
        )
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
        assert result.response.speech == {
            "plain": {"speech": expected, "extra_data": None}
        }

        unregister()


@pytest.mark.usefixtures("init_components", "sl_setup")
async def test_shopping_list_add_item(hass: HomeAssistant) -> None:
    """Test adding an item to the shopping list through the default agent."""
    result = await conversation.async_converse(
        hass, "add apples to my shopping list", None, Context()
    )
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.speech == {
        "plain": {"speech": "Added apples", "extra_data": None}
    }


@pytest.mark.usefixtures("init_components")
async def test_nevermind_intent(hass: HomeAssistant) -> None:
    """Test HassNevermind intent through the default agent."""
    result = await conversation.async_converse(hass, "nevermind", None, Context())
    assert result.response.intent is not None
    assert result.response.intent.intent_type == intent.INTENT_NEVERMIND

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert not result.response.speech


@pytest.mark.usefixtures("init_components")
async def test_respond_intent(hass: HomeAssistant) -> None:
    """Test HassRespond intent through the default agent."""
    result = await conversation.async_converse(hass, "hello", None, Context())
    assert result.response.intent is not None
    assert result.response.intent.intent_type == intent.INTENT_RESPOND

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "Hello from Home Assistant."


@pytest.mark.usefixtures("init_components")
async def test_device_area_context(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that including a device_id will target a specific area."""
    turn_on_calls = async_mock_service(hass, "light", "turn_on")
    turn_off_calls = async_mock_service(hass, "light", "turn_off")

    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")
    area_bedroom = area_registry.async_get_or_create("bedroom_id")
    area_bedroom = area_registry.async_update(area_bedroom.id, name="bedroom")

    # Create 2 lights in each area
    area_lights = defaultdict(list)
    all_lights = []
    for area in (area_kitchen, area_bedroom):
        for i in range(2):
            light_entity = entity_registry.async_get_or_create(
                "light", "demo", f"{area.name}-light-{i}"
            )
            light_entity = entity_registry.async_update_entity(
                light_entity.entity_id, area_id=area.id
            )
            hass.states.async_set(
                light_entity.entity_id,
                "off",
                attributes={ATTR_FRIENDLY_NAME: f"{area.name} light {i}"},
            )
            area_lights[area.id].append(light_entity)
            all_lights.append(light_entity)

    # Create voice satellites in each area
    entry = MockConfigEntry()
    entry.add_to_hass(hass)

    kitchen_satellite = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("demo", "id-satellite-kitchen")},
    )
    device_registry.async_update_device(kitchen_satellite.id, area_id=area_kitchen.id)

    bedroom_satellite = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("demo", "id-satellite-bedroom")},
    )
    device_registry.async_update_device(bedroom_satellite.id, area_id=area_bedroom.id)

    # Turn on lights in the area of a device
    result = await conversation.async_converse(
        hass,
        "turn on the lights",
        None,
        Context(),
        None,
        device_id=kitchen_satellite.id,
    )
    await hass.async_block_till_done()
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.intent is not None
    assert result.response.intent.slots["area"]["value"] == area_kitchen.id
    assert result.response.intent.slots["area"]["text"] == area_kitchen.normalized_name

    # Verify only kitchen lights were targeted
    assert {s.entity_id for s in result.response.matched_states} == {
        e.entity_id for e in area_lights[area_kitchen.id]
    }
    assert {c.data["entity_id"][0] for c in turn_on_calls} == {
        e.entity_id for e in area_lights[area_kitchen.id]
    }
    turn_on_calls.clear()

    # Ensure we can still target other areas by name
    result = await conversation.async_converse(
        hass,
        "turn on lights in the bedroom",
        None,
        Context(),
        None,
        device_id=kitchen_satellite.id,
    )
    await hass.async_block_till_done()
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.intent is not None
    assert result.response.intent.slots["area"]["value"] == area_bedroom.id
    assert result.response.intent.slots["area"]["text"] == area_bedroom.normalized_name

    # Verify only bedroom lights were targeted
    assert {s.entity_id for s in result.response.matched_states} == {
        e.entity_id for e in area_lights[area_bedroom.id]
    }
    assert {c.data["entity_id"][0] for c in turn_on_calls} == {
        e.entity_id for e in area_lights[area_bedroom.id]
    }
    turn_on_calls.clear()

    # Turn off all lights in the area of the other device
    result = await conversation.async_converse(
        hass,
        "turn lights off",
        None,
        Context(),
        None,
        device_id=bedroom_satellite.id,
    )
    await hass.async_block_till_done()
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.intent is not None
    assert result.response.intent.slots["area"]["value"] == area_bedroom.id
    assert result.response.intent.slots["area"]["text"] == area_bedroom.normalized_name

    # Verify only bedroom lights were targeted
    assert {s.entity_id for s in result.response.matched_states} == {
        e.entity_id for e in area_lights[area_bedroom.id]
    }
    assert {c.data["entity_id"][0] for c in turn_off_calls} == {
        e.entity_id for e in area_lights[area_bedroom.id]
    }
    turn_off_calls.clear()

    # Turn on/off all lights also works
    for command in ("on", "off"):
        result = await conversation.async_converse(
            hass, f"turn {command} all lights", None, Context(), None
        )
        await hass.async_block_till_done()
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE

        # All lights should have been targeted
        assert {s.entity_id for s in result.response.matched_states} == {
            e.entity_id for e in all_lights
        }


@pytest.mark.usefixtures("init_components")
async def test_error_no_device(hass: HomeAssistant) -> None:
    """Test error message when device/entity doesn't exist."""
    result = await conversation.async_converse(
        hass, "turn on missing entity", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any device called missing entity"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_device_exposed(hass: HomeAssistant) -> None:
    """Test error message when device/entity exists but is not exposed."""
    hass.states.async_set("light.kitchen_light", "off")
    expose_entity(hass, "light.kitchen_light", False)

    result = await conversation.async_converse(
        hass, "turn on kitchen light", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, kitchen light is not exposed"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_area(hass: HomeAssistant) -> None:
    """Test error message when area doesn't exist."""
    result = await conversation.async_converse(
        hass, "turn on the lights in missing area", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any area called missing area"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_floor(hass: HomeAssistant) -> None:
    """Test error message when floor doesn't exist."""
    result = await conversation.async_converse(
        hass, "turn on all the lights on missing floor", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any floor called missing"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_device_in_area(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """Test error message when area exists but is does not contain a device/entity."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")
    result = await conversation.async_converse(
        hass, "turn on missing entity in the kitchen", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any device called missing entity in the kitchen area"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_device_on_floor(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test error message when floor exists but is does not contain a device/entity."""
    floor_registry.async_create("ground")
    result = await conversation.async_converse(
        hass, "turn on missing entity on ground floor", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any device called missing entity on ground floor"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_device_on_floor_exposed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test error message when a device/entity exists on a floor but isn't exposed."""
    floor_ground = floor_registry.async_create("ground")

    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(
        area_kitchen.id, name="kitchen", floor_id=floor_ground.floor_id
    )

    kitchen_light = entity_registry.async_get_or_create("light", "demo", "1234")
    kitchen_light = entity_registry.async_update_entity(
        kitchen_light.entity_id,
        name="test light",
        area_id=area_kitchen.id,
    )
    hass.states.async_set(
        kitchen_light.entity_id,
        "off",
        attributes={ATTR_FRIENDLY_NAME: kitchen_light.name},
    )
    expose_entity(hass, kitchen_light.entity_id, False)
    await hass.async_block_till_done()

    # We don't have a sentence for turning on devices by floor
    name = MatchEntity(name="name", value=kitchen_light.name, text=kitchen_light.name)
    floor = MatchEntity(name="floor", value=floor_ground.name, text=floor_ground.name)
    recognize_result = RecognizeResult(
        intent=Intent("HassTurnOn"),
        intent_data=IntentData([]),
        entities={"name": name, "floor": floor},
        entities_list=[name, floor],
    )

    with patch(
        "homeassistant.components.conversation.default_agent.recognize_best",
        return_value=recognize_result,
    ):
        result = await conversation.async_converse(
            hass, "turn on test light on the ground floor", None, Context(), None
        )

        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code
            == intent.IntentResponseErrorCode.NO_VALID_TARGETS
        )
        assert (
            result.response.speech["plain"]["speech"]
            == "Sorry, test light in the ground floor is not exposed"
        )


@pytest.mark.usefixtures("init_components")
async def test_error_no_device_in_area_exposed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test error message when a device/entity exists in an area but isn't exposed."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")

    kitchen_light = entity_registry.async_get_or_create("light", "demo", "1234")
    kitchen_light = entity_registry.async_update_entity(
        kitchen_light.entity_id,
        name="test light",
        area_id=area_kitchen.id,
    )
    hass.states.async_set(
        kitchen_light.entity_id,
        "off",
        attributes={ATTR_FRIENDLY_NAME: kitchen_light.name},
    )
    expose_entity(hass, kitchen_light.entity_id, False)
    await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass, "turn on test light in the kitchen", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, test light in the kitchen area is not exposed"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_domain(hass: HomeAssistant) -> None:
    """Test error message when no devices/entities exist for a domain."""

    # We don't have a sentence for turning on all fans
    fan_domain = MatchEntity(name="domain", value="fan", text="fans")
    recognize_result = RecognizeResult(
        intent=Intent("HassTurnOn"),
        intent_data=IntentData([]),
        entities={"domain": fan_domain},
        entities_list=[fan_domain],
    )

    with patch(
        "homeassistant.components.conversation.default_agent.recognize_best",
        return_value=recognize_result,
    ):
        result = await conversation.async_converse(
            hass, "turn on the fans", None, Context(), None
        )

        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code
            == intent.IntentResponseErrorCode.NO_VALID_TARGETS
        )
        assert (
            result.response.speech["plain"]["speech"]
            == "Sorry, I am not aware of any fan"
        )


@pytest.mark.usefixtures("init_components")
async def test_error_no_domain_exposed(hass: HomeAssistant) -> None:
    """Test error message when devices/entities exist for a domain but are not exposed."""
    hass.states.async_set("fan.test_fan", "off")
    expose_entity(hass, "fan.test_fan", False)
    await hass.async_block_till_done()

    # We don't have a sentence for turning on all fans
    fan_domain = MatchEntity(name="domain", value="fan", text="fans")
    recognize_result = RecognizeResult(
        intent=Intent("HassTurnOn"),
        intent_data=IntentData([]),
        entities={"domain": fan_domain},
        entities_list=[fan_domain],
    )

    with patch(
        "homeassistant.components.conversation.default_agent.recognize_best",
        return_value=recognize_result,
    ):
        result = await conversation.async_converse(
            hass, "turn on the fans", None, Context(), None
        )

        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code
            == intent.IntentResponseErrorCode.NO_VALID_TARGETS
        )
        assert result.response.speech["plain"]["speech"] == "Sorry, no fan is exposed"


@pytest.mark.usefixtures("init_components")
async def test_error_no_domain_in_area(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """Test error message when no devices/entities for a domain exist in an area."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")
    result = await conversation.async_converse(
        hass, "turn on the lights in the kitchen", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any light in the kitchen area"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_domain_in_area_exposed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test error message when devices/entities for a domain exist in an area but are not exposed."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")

    kitchen_light = entity_registry.async_get_or_create("light", "demo", "1234")
    kitchen_light = entity_registry.async_update_entity(
        kitchen_light.entity_id,
        name="test light",
        area_id=area_kitchen.id,
    )
    hass.states.async_set(
        kitchen_light.entity_id,
        "off",
        attributes={ATTR_FRIENDLY_NAME: kitchen_light.name},
    )
    expose_entity(hass, kitchen_light.entity_id, False)
    await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass, "turn on the lights in the kitchen", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, no light in the kitchen area is exposed"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_domain_on_floor(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test error message when no devices/entities for a domain exist on a floor."""
    floor_ground = floor_registry.async_create("ground")
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(
        area_kitchen.id, name="kitchen", floor_id=floor_ground.floor_id
    )
    result = await conversation.async_converse(
        hass, "turn on all lights on the ground floor", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any light on the ground floor"
    )

    # Add a new floor/area to trigger registry event handlers
    floor_upstairs = floor_registry.async_create("upstairs")
    area_bedroom = area_registry.async_get_or_create("bedroom_id")
    area_bedroom = area_registry.async_update(
        area_bedroom.id, name="bedroom", floor_id=floor_upstairs.floor_id
    )

    result = await conversation.async_converse(
        hass, "turn on all lights upstairs", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any light on the upstairs floor"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_domain_on_floor_exposed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test error message when devices/entities for a domain exist on a floor but are not exposed."""
    floor_ground = floor_registry.async_create("ground")
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(
        area_kitchen.id, name="kitchen", floor_id=floor_ground.floor_id
    )
    kitchen_light = entity_registry.async_get_or_create("light", "demo", "1234")
    kitchen_light = entity_registry.async_update_entity(
        kitchen_light.entity_id,
        name="test light",
        area_id=area_kitchen.id,
    )
    hass.states.async_set(
        kitchen_light.entity_id,
        "off",
        attributes={ATTR_FRIENDLY_NAME: kitchen_light.name},
    )
    expose_entity(hass, kitchen_light.entity_id, False)
    await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass, "turn on all lights on the ground floor", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, no light in the ground floor is exposed"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_device_class(hass: HomeAssistant) -> None:
    """Test error message when no entities of a device class exist."""
    # Create a cover entity that is not a window.
    # This ensures that the filtering below won't exit early because there are
    # no entities in the cover domain.
    hass.states.async_set(
        "cover.garage_door",
        STATE_CLOSED,
        attributes={ATTR_DEVICE_CLASS: cover.CoverDeviceClass.GARAGE},
    )

    # We don't have a sentence for opening all windows
    cover_domain = MatchEntity(name="domain", value="cover", text="cover")
    window_class = MatchEntity(name="device_class", value="window", text="windows")
    recognize_result = RecognizeResult(
        intent=Intent("HassTurnOn"),
        intent_data=IntentData([]),
        entities={"domain": cover_domain, "device_class": window_class},
        entities_list=[cover_domain, window_class],
    )

    with patch(
        "homeassistant.components.conversation.default_agent.recognize_best",
        return_value=recognize_result,
    ):
        result = await conversation.async_converse(
            hass, "open the windows", None, Context(), None
        )

        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code
            == intent.IntentResponseErrorCode.NO_VALID_TARGETS
        )
        assert (
            result.response.speech["plain"]["speech"]
            == "Sorry, I am not aware of any window"
        )


@pytest.mark.usefixtures("init_components")
async def test_error_no_device_class_exposed(hass: HomeAssistant) -> None:
    """Test error message when entities of a device class exist but aren't exposed."""
    # Create a cover entity that is not a window.
    # This ensures that the filtering below won't exit early because there are
    # no entities in the cover domain.
    hass.states.async_set(
        "cover.garage_door",
        STATE_CLOSED,
        attributes={ATTR_DEVICE_CLASS: cover.CoverDeviceClass.GARAGE},
    )

    # Create a window an ensure it's not exposed
    hass.states.async_set(
        "cover.test_window",
        STATE_CLOSED,
        attributes={ATTR_DEVICE_CLASS: cover.CoverDeviceClass.WINDOW},
    )
    expose_entity(hass, "cover.test_window", False)

    # We don't have a sentence for opening all windows
    cover_domain = MatchEntity(name="domain", value="cover", text="cover")
    window_class = MatchEntity(name="device_class", value="window", text="windows")
    recognize_result = RecognizeResult(
        intent=Intent("HassTurnOn"),
        intent_data=IntentData([]),
        entities={"domain": cover_domain, "device_class": window_class},
        entities_list=[cover_domain, window_class],
    )

    with patch(
        "homeassistant.components.conversation.default_agent.recognize_best",
        return_value=recognize_result,
    ):
        result = await conversation.async_converse(
            hass, "open all the windows", None, Context(), None
        )

        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code
            == intent.IntentResponseErrorCode.NO_VALID_TARGETS
        )
        assert (
            result.response.speech["plain"]["speech"] == "Sorry, no window is exposed"
        )


@pytest.mark.usefixtures("init_components")
async def test_error_no_device_class_in_area(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """Test error message when no entities of a device class exist in an area."""
    area_bedroom = area_registry.async_get_or_create("bedroom_id")
    area_bedroom = area_registry.async_update(area_bedroom.id, name="bedroom")
    result = await conversation.async_converse(
        hass, "open bedroom windows", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any window in the bedroom area"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_device_class_in_area_exposed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test error message when entities of a device class exist in an area but are not exposed."""
    area_bedroom = area_registry.async_get_or_create("bedroom_id")
    area_bedroom = area_registry.async_update(area_bedroom.id, name="bedroom")
    bedroom_window = entity_registry.async_get_or_create("cover", "demo", "1234")
    bedroom_window = entity_registry.async_update_entity(
        bedroom_window.entity_id,
        name="test cover",
        area_id=area_bedroom.id,
    )
    hass.states.async_set(
        bedroom_window.entity_id,
        "off",
        attributes={ATTR_DEVICE_CLASS: cover.CoverDeviceClass.WINDOW},
    )
    expose_entity(hass, bedroom_window.entity_id, False)
    await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass, "open bedroom windows", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, no window in the bedroom area is exposed"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_device_class_on_floor_exposed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test error message when entities of a device class exist in on a floor but are not exposed."""
    floor_ground = floor_registry.async_create("ground")

    area_bedroom = area_registry.async_get_or_create("bedroom_id")
    area_bedroom = area_registry.async_update(
        area_bedroom.id, name="bedroom", floor_id=floor_ground.floor_id
    )
    bedroom_window = entity_registry.async_get_or_create("cover", "demo", "1234")
    bedroom_window = entity_registry.async_update_entity(
        bedroom_window.entity_id,
        name="test cover",
        area_id=area_bedroom.id,
    )
    hass.states.async_set(
        bedroom_window.entity_id,
        "off",
        attributes={ATTR_DEVICE_CLASS: cover.CoverDeviceClass.WINDOW},
    )
    expose_entity(hass, bedroom_window.entity_id, False)
    await hass.async_block_till_done()

    # We don't have a sentence for opening all windows on a floor
    cover_domain = MatchEntity(name="domain", value="cover", text="cover")
    window_class = MatchEntity(name="device_class", value="window", text="windows")
    floor = MatchEntity(name="floor", value=floor_ground.name, text=floor_ground.name)
    recognize_result = RecognizeResult(
        intent=Intent("HassTurnOn"),
        intent_data=IntentData([]),
        entities={"domain": cover_domain, "device_class": window_class, "floor": floor},
        entities_list=[cover_domain, window_class, floor],
    )

    with patch(
        "homeassistant.components.conversation.default_agent.recognize_best",
        return_value=recognize_result,
    ):
        result = await conversation.async_converse(
            hass, "open ground floor windows", None, Context(), None
        )

        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code
            == intent.IntentResponseErrorCode.NO_VALID_TARGETS
        )
        assert (
            result.response.speech["plain"]["speech"]
            == "Sorry, no window in the ground floor is exposed"
        )


@pytest.mark.usefixtures("init_components")
async def test_error_no_intent(hass: HomeAssistant) -> None:
    """Test response with an intent match failure."""
    with patch(
        "homeassistant.components.conversation.default_agent.recognize_best",
        return_value=None,
    ):
        result = await conversation.async_converse(
            hass, "do something", None, Context(), None
        )

        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code == intent.IntentResponseErrorCode.NO_INTENT_MATCH
        )
        assert (
            result.response.speech["plain"]["speech"]
            == "Sorry, I couldn't understand that"
        )


@pytest.mark.usefixtures("init_components")
async def test_error_duplicate_names(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test error message when multiple devices have the same name (or alias)."""
    kitchen_light_1 = entity_registry.async_get_or_create("light", "demo", "1234")
    kitchen_light_2 = entity_registry.async_get_or_create("light", "demo", "5678")

    # Same name and alias
    for light in (kitchen_light_1, kitchen_light_2):
        light = entity_registry.async_update_entity(
            light.entity_id,
            name="kitchen light",
            aliases={"overhead light"},
        )
        hass.states.async_set(
            light.entity_id,
            "off",
            attributes={ATTR_FRIENDLY_NAME: light.name},
        )

    # Check name and alias
    for name in ("kitchen light", "overhead light"):
        # command
        result = await conversation.async_converse(
            hass, f"turn on {name}", None, Context(), None
        )
        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code
            == intent.IntentResponseErrorCode.NO_VALID_TARGETS
        )
        assert (
            result.response.speech["plain"]["speech"]
            == f"Sorry, there are multiple devices called {name}"
        )

        # question
        result = await conversation.async_converse(
            hass, f"is {name} on?", None, Context(), None
        )
        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code
            == intent.IntentResponseErrorCode.NO_VALID_TARGETS
        )
        assert (
            result.response.speech["plain"]["speech"]
            == f"Sorry, there are multiple devices called {name}"
        )


@pytest.mark.usefixtures("init_components")
async def test_duplicate_names_but_one_is_exposed(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test when multiple devices have the same name (or alias), but only one of them is exposed."""
    kitchen_light_1 = entity_registry.async_get_or_create("light", "demo", "1234")
    kitchen_light_2 = entity_registry.async_get_or_create("light", "demo", "5678")

    # Same name and alias
    for light in (kitchen_light_1, kitchen_light_2):
        light = entity_registry.async_update_entity(
            light.entity_id,
            name="kitchen light",
            aliases={"overhead light"},
        )
        hass.states.async_set(
            light.entity_id,
            "off",
            attributes={ATTR_FRIENDLY_NAME: light.name},
        )

    # Only expose one
    expose_entity(hass, kitchen_light_1.entity_id, True)
    expose_entity(hass, kitchen_light_2.entity_id, False)

    # Check name and alias
    async_mock_service(hass, "light", "turn_on")
    for name in ("kitchen light", "overhead light"):
        # command
        result = await conversation.async_converse(
            hass, f"turn on {name}", None, Context(), None
        )
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
        assert result.response.matched_states[0].entity_id == kitchen_light_1.entity_id


@pytest.mark.usefixtures("init_components")
async def test_error_duplicate_names_same_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test error message when multiple devices have the same name (or alias) in the same area."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")

    kitchen_light_1 = entity_registry.async_get_or_create("light", "demo", "1234")
    kitchen_light_2 = entity_registry.async_get_or_create("light", "demo", "5678")

    # Same name and alias
    for light in (kitchen_light_1, kitchen_light_2):
        light = entity_registry.async_update_entity(
            light.entity_id,
            name="kitchen light",
            area_id=area_kitchen.id,
            aliases={"overhead light"},
        )
        hass.states.async_set(
            light.entity_id,
            "off",
            attributes={ATTR_FRIENDLY_NAME: light.name},
        )

    # Check name and alias
    for name in ("kitchen light", "overhead light"):
        # command
        result = await conversation.async_converse(
            hass, f"turn on {name} in {area_kitchen.name}", None, Context(), None
        )
        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code
            == intent.IntentResponseErrorCode.NO_VALID_TARGETS
        )
        assert (
            result.response.speech["plain"]["speech"]
            == f"Sorry, there are multiple devices called {name} in the {area_kitchen.name} area"
        )

        # question
        result = await conversation.async_converse(
            hass, f"is {name} on in the {area_kitchen.name}?", None, Context(), None
        )
        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code
            == intent.IntentResponseErrorCode.NO_VALID_TARGETS
        )
        assert (
            result.response.speech["plain"]["speech"]
            == f"Sorry, there are multiple devices called {name} in the {area_kitchen.name} area"
        )


@pytest.mark.usefixtures("init_components")
async def test_duplicate_names_same_area_but_one_is_exposed(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test when multiple devices have the same name (or alias) in the same area but only one is exposed."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")

    kitchen_light_1 = entity_registry.async_get_or_create("light", "demo", "1234")
    kitchen_light_2 = entity_registry.async_get_or_create("light", "demo", "5678")

    # Same name and alias
    for light in (kitchen_light_1, kitchen_light_2):
        light = entity_registry.async_update_entity(
            light.entity_id,
            name="kitchen light",
            area_id=area_kitchen.id,
            aliases={"overhead light"},
        )
        hass.states.async_set(
            light.entity_id,
            "off",
            attributes={ATTR_FRIENDLY_NAME: light.name},
        )

    # Only expose one
    expose_entity(hass, kitchen_light_1.entity_id, True)
    expose_entity(hass, kitchen_light_2.entity_id, False)

    # Check name and alias
    async_mock_service(hass, "light", "turn_on")
    for name in ("kitchen light", "overhead light"):
        # command
        result = await conversation.async_converse(
            hass, f"turn on {name} in {area_kitchen.name}", None, Context(), None
        )
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
        assert result.response.matched_states[0].entity_id == kitchen_light_1.entity_id


@pytest.mark.usefixtures("init_components")
async def test_duplicate_names_different_areas(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test preferred area when multiple devices have the same name (or alias) in different areas."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")

    area_bedroom = area_registry.async_get_or_create("bedroom_id")
    area_bedroom = area_registry.async_update(area_bedroom.id, name="bedroom")

    kitchen_light = entity_registry.async_get_or_create("light", "demo", "1234")
    kitchen_light = entity_registry.async_update_entity(
        kitchen_light.entity_id, area_id=area_kitchen.id
    )
    bedroom_light = entity_registry.async_get_or_create("light", "demo", "5678")
    bedroom_light = entity_registry.async_update_entity(
        bedroom_light.entity_id, area_id=area_bedroom.id
    )

    # Same name and alias
    for light in (kitchen_light, bedroom_light):
        light = entity_registry.async_update_entity(
            light.entity_id,
            name="test light",
            aliases={"overhead light"},
        )
        hass.states.async_set(
            light.entity_id,
            "off",
            attributes={ATTR_FRIENDLY_NAME: light.name},
        )

    # Add a satellite in the kitchen and bedroom
    kitchen_entry = MockConfigEntry()
    kitchen_entry.add_to_hass(hass)
    device_kitchen = device_registry.async_get_or_create(
        config_entry_id=kitchen_entry.entry_id,
        connections=set(),
        identifiers={("demo", "device-kitchen")},
    )
    device_registry.async_update_device(device_kitchen.id, area_id=area_kitchen.id)

    bedroom_entry = MockConfigEntry()
    bedroom_entry.add_to_hass(hass)
    device_bedroom = device_registry.async_get_or_create(
        config_entry_id=bedroom_entry.entry_id,
        connections=set(),
        identifiers={("demo", "device-bedroom")},
    )
    device_registry.async_update_device(device_bedroom.id, area_id=area_bedroom.id)

    # Check name and alias
    async_mock_service(hass, "light", "turn_on")
    for name in ("test light", "overhead light"):
        # Should fail without a preferred area
        result = await conversation.async_converse(
            hass, f"turn on {name}", None, Context(), None
        )
        assert result.response.response_type == intent.IntentResponseType.ERROR

        # Target kitchen light by using kitchen device
        result = await conversation.async_converse(
            hass, f"turn on {name}", None, Context(), None, device_id=device_kitchen.id
        )
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
        assert result.response.matched_states[0].entity_id == kitchen_light.entity_id

        # Target bedroom light by using bedroom device
        result = await conversation.async_converse(
            hass, f"turn on {name}", None, Context(), None, device_id=device_bedroom.id
        )
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
        assert result.response.matched_states[0].entity_id == bedroom_light.entity_id


@pytest.mark.usefixtures("init_components")
async def test_error_wrong_state(hass: HomeAssistant) -> None:
    """Test error message when no entities are in the correct state."""
    assert await async_setup_component(hass, media_player.DOMAIN, {})

    hass.states.async_set(
        "media_player.test_player",
        media_player.STATE_IDLE,
        {ATTR_FRIENDLY_NAME: "test player"},
    )

    result = await conversation.async_converse(
        hass, "pause test player", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert result.response.speech["plain"]["speech"] == "Sorry, no device is playing"


@pytest.mark.usefixtures("init_components")
async def test_error_feature_not_supported(hass: HomeAssistant) -> None:
    """Test error message when no devices support a required feature."""
    assert await async_setup_component(hass, media_player.DOMAIN, {})

    hass.states.async_set(
        "media_player.test_player",
        media_player.STATE_PLAYING,
        {ATTR_FRIENDLY_NAME: "test player"},
        # missing VOLUME_SET feature
    )

    result = await conversation.async_converse(
        hass, "set test player volume to 100%", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, no device supports the required features"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_no_timer_support(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test error message when a device does not support timers (no handler is registered)."""
    area_kitchen = area_registry.async_create("kitchen")

    entry = MockConfigEntry()
    entry.add_to_hass(hass)
    device_kitchen = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("demo", "device-kitchen")},
    )
    device_registry.async_update_device(device_kitchen.id, area_id=area_kitchen.id)
    device_id = device_kitchen.id

    # No timer handler is registered for the device
    result = await conversation.async_converse(
        hass, "set a 5 minute timer", None, Context(), None, device_id=device_id
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.FAILED_TO_HANDLE
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, timers are not supported on this device"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_timer_not_found(hass: HomeAssistant) -> None:
    """Test error message when a timer cannot be matched."""
    device_id = "test_device"

    @callback
    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        pass

    # Register a handler so the device "supports" timers
    async_register_timer_handler(hass, device_id, handle_timer)

    result = await conversation.async_converse(
        hass, "pause timer", None, Context(), None, device_id=device_id
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.FAILED_TO_HANDLE
    assert (
        result.response.speech["plain"]["speech"] == "Sorry, I couldn't find that timer"
    )


@pytest.mark.usefixtures("init_components")
async def test_error_multiple_timers_matched(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test error message when an intent would target multiple timers."""
    area_kitchen = area_registry.async_create("kitchen")

    # Starting a timer requires a device in an area
    entry = MockConfigEntry()
    entry.add_to_hass(hass)
    device_kitchen = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("demo", "device-kitchen")},
    )
    device_registry.async_update_device(device_kitchen.id, area_id=area_kitchen.id)
    device_id = device_kitchen.id

    @callback
    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        pass

    # Register a handler so the device "supports" timers
    async_register_timer_handler(hass, device_id, handle_timer)

    # Create two identical timers from the same device
    result = await conversation.async_converse(
        hass, "set a timer for 5 minutes", None, Context(), None, device_id=device_id
    )
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE

    result = await conversation.async_converse(
        hass, "set a timer for 5 minutes", None, Context(), None, device_id=device_id
    )
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE

    # Cannot target multiple timers
    result = await conversation.async_converse(
        hass, "cancel timer", None, Context(), None, device_id=device_id
    )
    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.FAILED_TO_HANDLE
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am unable to target multiple timers"
    )


@pytest.mark.usefixtures("init_components")
async def test_no_states_matched_default_error(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """Test default response when no states match and slots are missing."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")

    with patch(
        "homeassistant.components.conversation.default_agent.intent.async_handle",
        side_effect=intent.MatchFailedError(
            intent.MatchTargetsResult(False), intent.MatchTargetsConstraints()
        ),
    ):
        result = await conversation.async_converse(
            hass, "turn on lights in the kitchen", None, Context(), None
        )

        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code
            == intent.IntentResponseErrorCode.NO_VALID_TARGETS
        )
        assert (
            result.response.speech["plain"]["speech"]
            == "Sorry, I couldn't understand that"
        )


@pytest.mark.usefixtures("init_components")
async def test_empty_aliases(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test that empty aliases are not added to slot lists."""
    floor_1 = floor_registry.async_create("first floor", aliases={" "})

    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")
    area_kitchen = area_registry.async_update(
        area_kitchen.id, aliases={" "}, floor_id=floor_1.floor_id
    )

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
        kitchen_light.entity_id,
        device_id=kitchen_device.id,
        name="kitchen light",
        aliases={" "},
    )
    hass.states.async_set(
        kitchen_light.entity_id,
        "on",
        attributes={ATTR_FRIENDLY_NAME: kitchen_light.name},
    )

    with patch(
        "homeassistant.components.conversation.default_agent.DefaultAgent._recognize",
        return_value=None,
    ) as mock_recognize_all:
        await conversation.async_converse(
            hass, "turn on kitchen light", None, Context(), None
        )

        assert mock_recognize_all.call_count > 0
        slot_lists = mock_recognize_all.call_args[0][2]

        # Slot lists should only contain non-empty text
        assert slot_lists.keys() == {"area", "name", "floor"}
        areas = slot_lists["area"]
        assert len(areas.values) == 1
        assert areas.values[0].text_in.text == area_kitchen.normalized_name

        names = slot_lists["name"]
        assert len(names.values) == 1
        assert names.values[0].text_in.text == kitchen_light.name

        floors = slot_lists["floor"]
        assert len(floors.values) == 1
        assert floors.values[0].text_in.text == floor_1.name


@pytest.mark.usefixtures("init_components")
async def test_all_domains_loaded(hass: HomeAssistant) -> None:
    """Test that sentences for all domains are always loaded."""

    # light domain is not loaded
    assert "light" not in hass.config.components

    result = await conversation.async_converse(
        hass, "set brightness of test light to 100%", None, Context(), None
    )

    # Invalid target vs. no intent recognized
    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any device called test light"
    )


@pytest.mark.usefixtures("init_components")
async def test_same_named_entities_in_different_areas(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that entities with the same name in different areas can be targeted."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")

    area_bedroom = area_registry.async_get_or_create("bedroom_id")
    area_bedroom = area_registry.async_update(area_bedroom.id, name="bedroom")

    # Both lights have the same name, but are in different areas
    kitchen_light = entity_registry.async_get_or_create("light", "demo", "1234")
    kitchen_light = entity_registry.async_update_entity(
        kitchen_light.entity_id,
        area_id=area_kitchen.id,
        name="overhead light",
    )
    hass.states.async_set(
        kitchen_light.entity_id,
        "off",
        attributes={ATTR_FRIENDLY_NAME: kitchen_light.name},
    )

    bedroom_light = entity_registry.async_get_or_create("light", "demo", "5678")
    bedroom_light = entity_registry.async_update_entity(
        bedroom_light.entity_id,
        area_id=area_bedroom.id,
        name="overhead light",
    )
    hass.states.async_set(
        bedroom_light.entity_id,
        "off",
        attributes={ATTR_FRIENDLY_NAME: bedroom_light.name},
    )

    # Target kitchen light
    calls = async_mock_service(hass, "light", "turn_on")
    result = await conversation.async_converse(
        hass, "turn on overhead light in the kitchen", None, Context(), None
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.intent is not None
    assert (
        result.response.intent.slots.get("name", {}).get("value") == kitchen_light.name
    )
    assert (
        result.response.intent.slots.get("name", {}).get("text") == kitchen_light.name
    )
    assert len(result.response.matched_states) == 1
    assert result.response.matched_states[0].entity_id == kitchen_light.entity_id
    assert calls[0].data.get("entity_id") == [kitchen_light.entity_id]

    # Target bedroom light
    calls.clear()
    result = await conversation.async_converse(
        hass, "turn on overhead light in the bedroom", None, Context(), None
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.intent is not None
    assert (
        result.response.intent.slots.get("name", {}).get("value") == bedroom_light.name
    )
    assert (
        result.response.intent.slots.get("name", {}).get("text") == bedroom_light.name
    )
    assert len(result.response.matched_states) == 1
    assert result.response.matched_states[0].entity_id == bedroom_light.entity_id
    assert calls[0].data.get("entity_id") == [bedroom_light.entity_id]

    # Targeting a duplicate name should fail
    result = await conversation.async_converse(
        hass, "turn on overhead light", None, Context(), None
    )
    assert result.response.response_type == intent.IntentResponseType.ERROR

    # Querying a duplicate name should also fail
    result = await conversation.async_converse(
        hass, "is the overhead light on?", None, Context(), None
    )
    assert result.response.response_type == intent.IntentResponseType.ERROR

    # But we can still ask questions that don't rely on the name
    result = await conversation.async_converse(
        hass, "how many lights are on?", None, Context(), None
    )
    assert result.response.response_type == intent.IntentResponseType.QUERY_ANSWER


@pytest.mark.usefixtures("init_components")
async def test_same_aliased_entities_in_different_areas(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that entities with the same alias (but different names) in different areas can be targeted."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")

    area_bedroom = area_registry.async_get_or_create("bedroom_id")
    area_bedroom = area_registry.async_update(area_bedroom.id, name="bedroom")

    # Both lights have the same alias, but are in different areas
    kitchen_light = entity_registry.async_get_or_create("light", "demo", "1234")
    kitchen_light = entity_registry.async_update_entity(
        kitchen_light.entity_id,
        area_id=area_kitchen.id,
        name="kitchen overhead light",
        aliases={"overhead light"},
    )
    hass.states.async_set(
        kitchen_light.entity_id,
        "off",
        attributes={ATTR_FRIENDLY_NAME: kitchen_light.name},
    )

    bedroom_light = entity_registry.async_get_or_create("light", "demo", "5678")
    bedroom_light = entity_registry.async_update_entity(
        bedroom_light.entity_id,
        area_id=area_bedroom.id,
        name="bedroom overhead light",
        aliases={"overhead light"},
    )
    hass.states.async_set(
        bedroom_light.entity_id,
        "off",
        attributes={ATTR_FRIENDLY_NAME: bedroom_light.name},
    )

    # Target kitchen light
    calls = async_mock_service(hass, "light", "turn_on")
    result = await conversation.async_converse(
        hass, "turn on overhead light in the kitchen", None, Context(), None
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.intent is not None
    assert result.response.intent.slots.get("name", {}).get("value") == "overhead light"
    assert result.response.intent.slots.get("name", {}).get("text") == "overhead light"
    assert len(result.response.matched_states) == 1
    assert result.response.matched_states[0].entity_id == kitchen_light.entity_id
    assert calls[0].data.get("entity_id") == [kitchen_light.entity_id]

    # Target bedroom light
    calls.clear()
    result = await conversation.async_converse(
        hass, "turn on overhead light in the bedroom", None, Context(), None
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.intent is not None
    assert result.response.intent.slots.get("name", {}).get("value") == "overhead light"
    assert result.response.intent.slots.get("name", {}).get("text") == "overhead light"
    assert len(result.response.matched_states) == 1
    assert result.response.matched_states[0].entity_id == bedroom_light.entity_id
    assert calls[0].data.get("entity_id") == [bedroom_light.entity_id]

    # Targeting a duplicate alias should fail
    result = await conversation.async_converse(
        hass, "turn on overhead light", None, Context(), None
    )
    assert result.response.response_type == intent.IntentResponseType.ERROR

    # Querying a duplicate alias should also fail
    result = await conversation.async_converse(
        hass, "is the overhead light on?", None, Context(), None
    )
    assert result.response.response_type == intent.IntentResponseType.ERROR

    # But we can still ask questions that don't rely on the alias
    result = await conversation.async_converse(
        hass, "how many lights are on?", None, Context(), None
    )
    assert result.response.response_type == intent.IntentResponseType.QUERY_ANSWER


@pytest.mark.usefixtures("init_components")
async def test_device_id_in_handler(hass: HomeAssistant) -> None:
    """Test that the default agent passes device_id to intent handler."""
    device_id = "test_device"

    # Reuse custom sentences in test config to trigger default agent.
    class OrderBeerIntentHandler(intent.IntentHandler):
        intent_type = "OrderBeer"

        def __init__(self) -> None:
            super().__init__()
            self.device_id: str | None = None

        async def async_handle(
            self, intent_obj: intent.Intent
        ) -> intent.IntentResponse:
            self.device_id = intent_obj.device_id
            return intent_obj.create_response()

    handler = OrderBeerIntentHandler()
    intent.async_register(hass, handler)

    result = await conversation.async_converse(
        hass,
        "I'd like to order a stout please",
        None,
        Context(),
        device_id=device_id,
    )
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert handler.device_id == device_id


@pytest.mark.usefixtures("init_components")
async def test_name_wildcard_lower_priority(hass: HomeAssistant) -> None:
    """Test that the default agent does not prioritize a {name} slot when it's a wildcard."""

    class OrderBeerIntentHandler(intent.IntentHandler):
        intent_type = "OrderBeer"

        def __init__(self) -> None:
            super().__init__()
            self.triggered = False

        async def async_handle(
            self, intent_obj: intent.Intent
        ) -> intent.IntentResponse:
            self.triggered = True
            return intent_obj.create_response()

    class OrderFoodIntentHandler(intent.IntentHandler):
        intent_type = "OrderFood"

        def __init__(self) -> None:
            super().__init__()
            self.triggered = False

        async def async_handle(
            self, intent_obj: intent.Intent
        ) -> intent.IntentResponse:
            self.triggered = True
            return intent_obj.create_response()

    beer_handler = OrderBeerIntentHandler()
    food_handler = OrderFoodIntentHandler()
    intent.async_register(hass, beer_handler)
    intent.async_register(hass, food_handler)

    # Matches OrderBeer because more literal text is matched ("a")
    result = await conversation.async_converse(
        hass, "I'd like to order a stout please", None, Context(), None
    )
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert beer_handler.triggered
    assert not food_handler.triggered

    # Matches OrderFood because "cookie" is not in the beer styles list
    beer_handler.triggered = False
    result = await conversation.async_converse(
        hass, "I'd like to order a cookie please", None, Context(), None
    )
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert not beer_handler.triggered
    assert food_handler.triggered


async def test_intent_entity_added_removed(
    hass: HomeAssistant,
    init_components,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test processing intent via HTTP API with entities added later.

    We want to ensure that adding an entity later busts the cache
    so that the new entity is available as well as any aliases.
    """
    context = Context()
    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="kitchen"
    )
    entity_registry.async_update_entity("light.kitchen", aliases={"my cool light"})
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", "off")

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    result = await conversation.async_converse(
        hass, "turn on my cool light", None, context
    )

    assert len(calls) == 1
    data = result.as_dict()

    assert data == snapshot
    assert data["response"]["response_type"] == "action_done"

    # Add an entity
    entity_registry.async_get_or_create(
        "light", "demo", "5678", suggested_object_id="late"
    )
    hass.states.async_set("light.late", "off", {"friendly_name": "friendly light"})

    result = await conversation.async_converse(
        hass, "turn on friendly light", None, context
    )
    data = result.as_dict()

    assert data == snapshot
    assert data["response"]["response_type"] == "action_done"

    # Now add an alias
    entity_registry.async_update_entity("light.late", aliases={"late added light"})

    result = await conversation.async_converse(
        hass, "turn on late added light", None, context
    )

    data = result.as_dict()

    assert data == snapshot
    assert data["response"]["response_type"] == "action_done"

    # Now delete the entity
    hass.states.async_remove("light.late")

    result = await conversation.async_converse(
        hass, "turn on late added light", None, context
    )
    data = result.as_dict()
    assert data == snapshot
    assert data["response"]["response_type"] == "error"


async def test_intent_alias_added_removed(
    hass: HomeAssistant,
    init_components,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test processing intent via HTTP API with aliases added later.

    We want to ensure that adding an alias later busts the cache
    so that the new alias is available.
    """
    context = Context()
    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="kitchen"
    )
    hass.states.async_set("light.kitchen", "off", {"friendly_name": "kitchen light"})

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    result = await conversation.async_converse(
        hass, "turn on kitchen light", None, context
    )
    assert len(calls) == 1
    data = result.as_dict()

    assert data == snapshot
    assert data["response"]["response_type"] == "action_done"

    # Add an alias
    entity_registry.async_update_entity("light.kitchen", aliases={"late added alias"})

    result = await conversation.async_converse(
        hass, "turn on late added alias", None, context
    )

    data = result.as_dict()

    assert data == snapshot
    assert data["response"]["response_type"] == "action_done"

    # Now remove the alieas
    entity_registry.async_update_entity("light.kitchen", aliases={})

    result = await conversation.async_converse(
        hass, "turn on late added alias", None, context
    )

    data = result.as_dict()
    assert data == snapshot
    assert data["response"]["response_type"] == "error"


async def test_intent_entity_renamed(
    hass: HomeAssistant,
    init_components,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test processing intent via HTTP API with entities renamed later.

    We want to ensure that renaming an entity later busts the cache
    so that the new name is used.
    """
    context = Context()
    entity = MockLight("kitchen light", STATE_ON)
    entity._attr_unique_id = "1234"
    entity.entity_id = "light.kitchen"
    setup_test_component_platform(hass, LIGHT_DOMAIN, [entity])

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {LIGHT_DOMAIN: [{"platform": "test"}]},
    )
    await hass.async_block_till_done()

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    result = await conversation.async_converse(
        hass, "turn on kitchen light", None, context
    )

    assert len(calls) == 1
    data = result.as_dict()

    assert data == snapshot
    assert data["response"]["response_type"] == "action_done"

    # Rename the entity
    entity_registry.async_update_entity("light.kitchen", name="renamed light")
    await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass, "turn on renamed light", None, context
    )

    data = result.as_dict()

    assert data == snapshot
    assert data["response"]["response_type"] == "action_done"


async def test_intent_entity_remove_custom_name(
    hass: HomeAssistant,
    init_components,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that removing a custom name allows targeting the entity by its auto-generated name again."""
    context = Context()
    entity = MockLight("kitchen light", STATE_ON)
    entity._attr_unique_id = "1234"
    entity.entity_id = "light.kitchen"
    setup_test_component_platform(hass, LIGHT_DOMAIN, [entity])

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {LIGHT_DOMAIN: [{"platform": "test"}]},
    )
    await hass.async_block_till_done()

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    # Should fail with auto-generated name
    entity_registry.async_update_entity("light.kitchen", name="renamed light")
    result = await conversation.async_converse(
        hass, "turn on kitchen light", None, context
    )

    data = result.as_dict()
    assert data == snapshot
    assert data["response"]["response_type"] == "error"

    # Now clear the custom name
    entity_registry.async_update_entity("light.kitchen", name=None)
    await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass, "turn on kitchen light", None, context
    )

    data = result.as_dict()

    assert data == snapshot
    assert data["response"]["response_type"] == "action_done"
    assert len(calls) == 1

    result = await conversation.async_converse(
        hass, "turn on renamed light", None, context
    )

    data = result.as_dict()
    assert data == snapshot
    assert data["response"]["response_type"] == "error"


async def test_intent_entity_fail_if_unexposed(
    hass: HomeAssistant,
    init_components,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that an entity is not usable if unexposed."""
    context = Context()
    entity = MockLight("kitchen light", STATE_ON)
    entity._attr_unique_id = "1234"
    entity.entity_id = "light.kitchen"
    setup_test_component_platform(hass, LIGHT_DOMAIN, [entity])

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {LIGHT_DOMAIN: [{"platform": "test"}]},
    )
    await hass.async_block_till_done()

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    # Unexpose the entity
    expose_entity(hass, "light.kitchen", False)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await conversation.async_converse(
        hass, "turn on kitchen light", None, context
    )

    data = result.as_dict()
    assert data == snapshot
    assert data["response"]["response_type"] == "error"
    assert len(calls) == 0


async def test_intent_entity_exposed(
    hass: HomeAssistant,
    init_components,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test processing intent via HTTP API with manual expose.

    We want to ensure that manually exposing an entity later busts the cache
    so that the new setting is used.
    """
    context = Context()
    entity = MockLight("kitchen light", STATE_ON)
    entity._attr_unique_id = "1234"
    entity.entity_id = "light.kitchen"
    setup_test_component_platform(hass, LIGHT_DOMAIN, [entity])

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {LIGHT_DOMAIN: [{"platform": "test"}]},
    )
    await hass.async_block_till_done()

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    # Unexpose, then expose the entity
    expose_entity(hass, "light.kitchen", False)
    await hass.async_block_till_done()
    expose_entity(hass, "light.kitchen", True)
    await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass, "turn on kitchen light", None, context
    )

    data = result.as_dict()
    assert data == snapshot
    assert data["response"]["response_type"] == "action_done"
    assert len(calls) == 1


async def test_intent_conversion_not_expose_new(
    hass: HomeAssistant,
    init_components,
    hass_admin_user: MockUser,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test processing intent via HTTP API when not exposing new entities."""
    # Disable exposing new entities to the default agent
    expose_new(hass, False)

    context = Context()
    entity = MockLight("kitchen light", STATE_ON)
    entity._attr_unique_id = "1234"
    entity.entity_id = "light.kitchen"
    setup_test_component_platform(hass, LIGHT_DOMAIN, [entity])

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {LIGHT_DOMAIN: [{"platform": "test"}]},
    )
    await hass.async_block_till_done()

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    result = await conversation.async_converse(
        hass, "turn on kitchen light", None, context
    )

    data = result.as_dict()
    assert data == snapshot
    assert data["response"]["response_type"] == "error"

    # Expose the entity
    expose_entity(hass, "light.kitchen", True)
    await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass, "turn on kitchen light", None, context
    )

    assert len(calls) == 1
    data = result.as_dict()

    assert data == snapshot
    assert data["response"]["response_type"] == "action_done"


async def test_custom_sentences(
    hass: HomeAssistant,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test custom sentences with a custom intent."""
    # Expecting testing_config/custom_sentences/en/beer.yaml
    intent.async_register(hass, OrderBeerIntentHandler())

    # Don't use "en" to test loading custom sentences with language variants.
    language = "en-us"

    # Invoke intent via HTTP API
    for beer_style in ("stout", "lager"):
        result = await conversation.async_converse(
            hass,
            f"I'd like to order a {beer_style}, please",
            None,
            Context(),
            language=language,
        )

        data = result.as_dict()
        assert data == snapshot
        assert data["response"]["response_type"] == "action_done"
        assert (
            data["response"]["speech"]["plain"]["speech"]
            == f"You ordered a {beer_style}"
        )


async def test_custom_sentences_config(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test custom sentences with a custom intent in config."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(
        hass,
        "conversation",
        {"conversation": {"intents": {"StealthMode": ["engage stealth mode"]}}},
    )
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(
        hass,
        "intent_script",
        {
            "intent_script": {
                "StealthMode": {"speech": {"text": "Stealth mode engaged"}}
            }
        },
    )

    # Invoke intent via HTTP API
    result = await conversation.async_converse(
        hass, "engage stealth mode", None, Context(), None
    )

    data = result.as_dict()
    assert data == snapshot
    assert data["response"]["response_type"] == "action_done"
    assert data["response"]["speech"]["plain"]["speech"] == "Stealth mode engaged"


async def test_language_region(hass: HomeAssistant, init_components) -> None:
    """Test regional languages."""
    hass.states.async_set("light.kitchen", "off")
    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    # Add fake region
    language = f"{hass.config.language}-YZ"
    await hass.services.async_call(
        "conversation",
        "process",
        {
            conversation.ATTR_TEXT: "turn on the kitchen",
            conversation.ATTR_LANGUAGE: language,
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == LIGHT_DOMAIN
    assert call.service == "turn_on"
    assert call.data == {"entity_id": ["light.kitchen"]}


async def test_non_default_response(hass: HomeAssistant, init_components) -> None:
    """Test intent response that is not the default."""
    hass.states.async_set("cover.front_door", "closed")
    calls = async_mock_service(hass, "cover", SERVICE_OPEN_COVER)

    agent = hass.data[DATA_DEFAULT_ENTITY]
    assert isinstance(agent, default_agent.DefaultAgent)

    result = await agent.async_process(
        ConversationInput(
            text="open the front door",
            context=Context(),
            conversation_id=None,
            device_id=None,
            language=hass.config.language,
            agent_id=None,
        )
    )
    assert len(calls) == 1
    assert result.response.speech["plain"]["speech"] == "Opened"


async def test_turn_on_area(
    hass: HomeAssistant,
    init_components,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test turning on an area."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    kitchen_area = area_registry.async_create("kitchen")
    device_registry.async_update_device(device.id, area_id=kitchen_area.id)

    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="stove"
    )
    entity_registry.async_update_entity(
        "light.stove", aliases={"my stove light"}, area_id=kitchen_area.id
    )
    hass.states.async_set("light.stove", "off")

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    await hass.services.async_call(
        "conversation",
        "process",
        {conversation.ATTR_TEXT: "turn on lights in the kitchen"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == LIGHT_DOMAIN
    assert call.service == "turn_on"
    assert call.data == {"entity_id": ["light.stove"]}

    basement_area = area_registry.async_create("basement")
    device_registry.async_update_device(device.id, area_id=basement_area.id)
    entity_registry.async_update_entity("light.stove", area_id=basement_area.id)
    calls.clear()

    # Test that the area is updated
    await hass.services.async_call(
        "conversation",
        "process",
        {conversation.ATTR_TEXT: "turn on lights in the kitchen"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 0

    # Test the new area works
    await hass.services.async_call(
        "conversation",
        "process",
        {conversation.ATTR_TEXT: "turn on lights in the basement"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == LIGHT_DOMAIN
    assert call.service == "turn_on"
    assert call.data == {"entity_id": ["light.stove"]}


async def test_light_area_same_name(
    hass: HomeAssistant,
    init_components,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test turning on a light with the same name as an area."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    kitchen_area = area_registry.async_create("kitchen")
    device_registry.async_update_device(device.id, area_id=kitchen_area.id)

    kitchen_light = entity_registry.async_get_or_create(
        "light", "demo", "1234", original_name="light in the kitchen"
    )
    entity_registry.async_update_entity(
        kitchen_light.entity_id, area_id=kitchen_area.id
    )
    hass.states.async_set(
        kitchen_light.entity_id,
        "off",
        attributes={ATTR_FRIENDLY_NAME: "light in the kitchen"},
    )

    ceiling_light = entity_registry.async_get_or_create(
        "light", "demo", "5678", original_name="ceiling light"
    )
    entity_registry.async_update_entity(
        ceiling_light.entity_id, area_id=kitchen_area.id
    )
    hass.states.async_set(
        ceiling_light.entity_id, "off", attributes={ATTR_FRIENDLY_NAME: "ceiling light"}
    )

    bathroom_light = entity_registry.async_get_or_create(
        "light", "demo", "9012", original_name="light"
    )
    hass.states.async_set(
        bathroom_light.entity_id, "off", attributes={ATTR_FRIENDLY_NAME: "light"}
    )

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    await hass.services.async_call(
        "conversation",
        "process",
        {conversation.ATTR_TEXT: "turn on light in the kitchen"},
    )
    await hass.async_block_till_done()

    # Should only turn on one light instead of all lights in the kitchen
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == LIGHT_DOMAIN
    assert call.service == "turn_on"
    assert call.data == {"entity_id": [kitchen_light.entity_id]}


async def test_custom_sentences_priority(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that user intents from custom_sentences have priority over builtin intents/sentences."""
    with tempfile.NamedTemporaryFile(
        mode="w+",
        encoding="utf-8",
        suffix=".yaml",
        dir=os.path.join(hass.config.config_dir, "custom_sentences", "en"),
    ) as custom_sentences_file:
        # Add a custom sentence that would match a builtin sentence.
        # Custom sentences have priority.
        yaml.dump(
            {
                "language": "en",
                "intents": {
                    "CustomIntent": {"data": [{"sentences": ["turn on the lamp"]}]}
                },
            },
            custom_sentences_file,
        )
        custom_sentences_file.flush()
        custom_sentences_file.seek(0)

        assert await async_setup_component(hass, "homeassistant", {})
        assert await async_setup_component(hass, "conversation", {})
        assert await async_setup_component(hass, "light", {})
        assert await async_setup_component(hass, "intent", {})
        assert await async_setup_component(
            hass,
            "intent_script",
            {
                "intent_script": {
                    "CustomIntent": {"speech": {"text": "custom response"}}
                }
            },
        )

        # Ensure that a "lamp" exists so that we can verify the custom intent
        # overrides the builtin sentence.
        hass.states.async_set("light.lamp", "off")

        result = await conversation.async_converse(
            hass,
            "turn on the lamp",
            None,
            Context(),
            language=hass.config.language,
        )

        data = result.as_dict()
        assert data["response"]["response_type"] == "action_done"
        assert data["response"]["speech"]["plain"]["speech"] == "custom response"


async def test_config_sentences_priority(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that user intents from configuration.yaml have priority over builtin intents/sentences.

    Also test that they follow proper selection logic.
    """
    # Add a custom sentence that would match a builtin sentence.
    # Custom sentences have priority.
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(
        hass,
        "conversation",
        {
            "conversation": {
                "intents": {
                    "CustomIntent": ["turn on <name>"],
                    "WorseCustomIntent": ["turn on the lamp"],
                    "FakeCustomIntent": ["turn on <name>"],
                }
            }
        },
    )

    # Fake intent not being custom
    intents = (
        await conversation.async_get_agent(hass).async_get_or_load_intents(
            hass.config.language
        )
    ).intents.intents
    intents["FakeCustomIntent"].data[0].metadata[METADATA_CUSTOM_SENTENCE] = False

    assert await async_setup_component(hass, "light", {})
    assert await async_setup_component(
        hass,
        "intent_script",
        {
            "intent_script": {
                "CustomIntent": {"speech": {"text": "custom response"}},
                "WorseCustomIntent": {"speech": {"text": "worse custom response"}},
                "FakeCustomIntent": {"speech": {"text": "fake custom response"}},
            }
        },
    )

    # Ensure that a "lamp" exists so that we can verify the custom intent
    # overrides the builtin sentence.
    hass.states.async_set("light.lamp", "off")

    result = await conversation.async_converse(
        hass,
        "turn on the lamp",
        None,
        Context(),
        language=hass.config.language,
    )
    data = result.as_dict()
    assert data["response"]["response_type"] == "action_done"
    assert data["response"]["speech"]["plain"]["speech"] == "custom response"


async def test_query_same_name_different_areas(
    hass: HomeAssistant,
    init_components,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test asking a question about entities with the same name in different areas."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)

    kitchen_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    kitchen_area = area_registry.async_create("kitchen")
    device_registry.async_update_device(kitchen_device.id, area_id=kitchen_area.id)

    kitchen_light = entity_registry.async_get_or_create(
        "light",
        "demo",
        "1234",
    )
    entity_registry.async_update_entity(
        kitchen_light.entity_id, area_id=kitchen_area.id
    )
    hass.states.async_set(
        kitchen_light.entity_id,
        "on",
        attributes={ATTR_FRIENDLY_NAME: "overhead light"},
    )

    bedroom_area = area_registry.async_create("bedroom")
    bedroom_light = entity_registry.async_get_or_create(
        "light",
        "demo",
        "5678",
    )
    entity_registry.async_update_entity(
        bedroom_light.entity_id, area_id=bedroom_area.id
    )
    hass.states.async_set(
        bedroom_light.entity_id,
        "off",
        attributes={ATTR_FRIENDLY_NAME: "overhead light"},
    )

    # Should fail without a preferred area (duplicate name)
    result = await conversation.async_converse(
        hass, "is the overhead light on?", None, Context(), None
    )
    assert result.response.response_type == intent.IntentResponseType.ERROR

    # Succeeds using area from device (kitchen)
    result = await conversation.async_converse(
        hass,
        "is the overhead light on?",
        None,
        Context(),
        None,
        device_id=kitchen_device.id,
    )
    assert result.response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(result.response.matched_states) == 1
    assert result.response.matched_states[0].entity_id == kitchen_light.entity_id


@pytest.mark.usefixtures("init_components")
async def test_intent_cache_exposed(hass: HomeAssistant) -> None:
    """Test that intent recognition results are cached for exposed entities."""
    agent = hass.data[DATA_DEFAULT_ENTITY]
    assert isinstance(agent, default_agent.DefaultAgent)

    entity_id = "light.test_light"
    hass.states.async_set(entity_id, "off")
    expose_entity(hass, entity_id, True)
    await hass.async_block_till_done()

    user_input = ConversationInput(
        text="turn on test light",
        context=Context(),
        conversation_id=None,
        device_id=None,
        language=hass.config.language,
        agent_id=None,
    )
    result = await agent.async_recognize_intent(user_input)
    assert result is not None
    assert result.entities["name"].text == "test light"

    # Mark this result so we know it is from cache next time
    mark = "_from_cache"
    setattr(result, mark, True)

    # Should be from cache this time
    result = await agent.async_recognize_intent(user_input)
    assert result is not None
    assert getattr(result, mark, None) is True

    # Unexposing clears the cache
    expose_entity(hass, entity_id, False)
    result = await agent.async_recognize_intent(user_input)
    assert result is not None
    assert getattr(result, mark, None) is None


@pytest.mark.usefixtures("init_components")
async def test_intent_cache_all_entities(hass: HomeAssistant) -> None:
    """Test that intent recognition results are cached for all entities."""
    agent = hass.data[DATA_DEFAULT_ENTITY]
    assert isinstance(agent, default_agent.DefaultAgent)

    entity_id = "light.test_light"
    hass.states.async_set(entity_id, "off")
    expose_entity(hass, entity_id, False)  # not exposed
    await hass.async_block_till_done()

    user_input = ConversationInput(
        text="turn on test light",
        context=Context(),
        conversation_id=None,
        device_id=None,
        language=hass.config.language,
        agent_id=None,
    )
    result = await agent.async_recognize_intent(user_input)
    assert result is not None
    assert result.entities["name"].text == "test light"

    # Mark this result so we know it is from cache next time
    mark = "_from_cache"
    setattr(result, mark, True)

    # Should be from cache this time
    result = await agent.async_recognize_intent(user_input)
    assert result is not None
    assert getattr(result, mark, None) is True

    # Adding a new entity clears the cache
    hass.states.async_set("light.new_light", "off")
    result = await agent.async_recognize_intent(user_input)
    assert result is not None
    assert getattr(result, mark, None) is None


@pytest.mark.usefixtures("init_components")
async def test_intent_cache_fuzzy(hass: HomeAssistant) -> None:
    """Test that intent recognition results are cached for fuzzy matches."""
    agent = hass.data[DATA_DEFAULT_ENTITY]
    assert isinstance(agent, default_agent.DefaultAgent)

    # There is no entity named test light
    user_input = ConversationInput(
        text="turn on test light",
        context=Context(),
        conversation_id=None,
        device_id=None,
        language=hass.config.language,
        agent_id=None,
    )
    result = await agent.async_recognize_intent(user_input)
    assert result is not None
    assert result.unmatched_entities["area"].text == "test "

    # Mark this result so we know it is from cache next time
    mark = "_from_cache"
    setattr(result, mark, True)

    # Should be from cache this time
    result = await agent.async_recognize_intent(user_input)
    assert result is not None
    assert getattr(result, mark, None) is True


@pytest.mark.usefixtures("init_components")
async def test_entities_filtered_by_input(hass: HomeAssistant) -> None:
    """Test that entities are filtered by the input text before intent matching."""
    agent = hass.data[DATA_DEFAULT_ENTITY]
    assert isinstance(agent, default_agent.DefaultAgent)

    # Only the switch is exposed
    hass.states.async_set("light.test_light", "off")
    hass.states.async_set(
        "light.test_light_2", "off", attributes={ATTR_FRIENDLY_NAME: "test light"}
    )
    hass.states.async_set("cover.garage_door", "closed")
    hass.states.async_set("switch.test_switch", "off")
    expose_entity(hass, "light.test_light", False)
    expose_entity(hass, "light.test_light_2", False)
    expose_entity(hass, "cover.garage_door", False)
    expose_entity(hass, "switch.test_switch", True)
    await hass.async_block_till_done()

    # test switch is exposed
    user_input = ConversationInput(
        text="turn on test switch",
        context=Context(),
        conversation_id=None,
        device_id=None,
        language=hass.config.language,
        agent_id=None,
    )

    with patch(
        "homeassistant.components.conversation.default_agent.recognize_best",
        return_value=None,
    ) as recognize_best:
        await agent.async_recognize_intent(user_input)

        # (1) exposed, (2) all entities
        assert len(recognize_best.call_args_list) == 2

        # Only the test light should have been considered because its name shows
        # up in the input text.
        slot_lists = recognize_best.call_args_list[0].kwargs["slot_lists"]
        name_list = slot_lists["name"]
        assert len(name_list.values) == 1
        assert name_list.values[0].text_in.text == "test switch"

    # test light is not exposed
    user_input = ConversationInput(
        text="turn on Test Light",  # different casing for name
        context=Context(),
        conversation_id=None,
        device_id=None,
        language=hass.config.language,
        agent_id=None,
    )

    with patch(
        "homeassistant.components.conversation.default_agent.recognize_best",
        return_value=None,
    ) as recognize_best:
        await agent.async_recognize_intent(user_input)

        # (1) exposed, (2) all entities
        assert len(recognize_best.call_args_list) == 2

        # Both test lights should have been considered because their name shows
        # up in the input text.
        slot_lists = recognize_best.call_args_list[1].kwargs["slot_lists"]
        name_list = slot_lists["name"]
        assert len(name_list.values) == 2
        assert name_list.values[0].text_in.text == "test light"
        assert name_list.values[1].text_in.text == "test light"


@pytest.mark.usefixtures("init_components")
async def test_entities_names_are_not_templates(hass: HomeAssistant) -> None:
    """Test that entities names are not treated as hassil templates."""
    # Contains hassil template characters
    hass.states.async_set(
        "light.test_light", "off", attributes={ATTR_FRIENDLY_NAME: "<test [light"}
    )

    async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    # Exposed
    result = await conversation.async_converse(
        hass,
        "turn on <test [light",
        None,
        Context(),
        language=hass.config.language,
    )

    assert result is not None
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE

    # Not exposed
    expose_entity(hass, "light.test_light", False)
    result = await conversation.async_converse(
        hass,
        "turn on <test [light",
        None,
        Context(),
        language=hass.config.language,
    )

    assert result is not None
    assert result.response.response_type == intent.IntentResponseType.ERROR


@pytest.mark.parametrize(
    ("language", "light_name", "on_sentence", "off_sentence"),
    [
        ("en", "test light", "turn on test light", "turn off test light"),
        ("de", "Testlicht", "Schalte Testlicht ein", "Schalte Testlicht aus"),
        (
            "fr",
            "lumière de test",
            "Allumer la lumière de test",
            "Éteindre la lumière de test",
        ),
        ("nl", "testlicht", "Zet testlicht aan", "Zet testlicht uit"),
        ("zh-cn", "卧室灯", "打开卧室灯", "关闭卧室灯"),
        ("zh-hk", "睡房燈", "打開睡房燈", "關閉睡房燈"),
        ("zh-tw", "臥室檯燈", "打開臥室檯燈", "關臥室檯燈"),
    ],
)
@pytest.mark.usefixtures("init_components")
async def test_turn_on_off(
    hass: HomeAssistant,
    language: str,
    light_name: str,
    on_sentence: str,
    off_sentence: str,
) -> None:
    """Test turn on/off in multiple languages."""
    entity_id = "light.light1234"
    hass.states.async_set(
        entity_id, STATE_OFF, attributes={ATTR_FRIENDLY_NAME: light_name}
    )

    on_calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    await conversation.async_converse(
        hass,
        on_sentence,
        None,
        Context(),
        language=language,
    )
    assert len(on_calls) == 1
    assert on_calls[0].data.get("entity_id") == [entity_id]

    off_calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_off")
    await conversation.async_converse(
        hass,
        off_sentence,
        None,
        Context(),
        language=language,
    )
    assert len(off_calls) == 1
    assert off_calls[0].data.get("entity_id") == [entity_id]


@pytest.mark.parametrize(
    ("error_code", "return_response"),
    [
        (intent.IntentResponseErrorCode.NO_INTENT_MATCH, False),
        (intent.IntentResponseErrorCode.NO_VALID_TARGETS, False),
        (intent.IntentResponseErrorCode.FAILED_TO_HANDLE, True),
        (intent.IntentResponseErrorCode.UNKNOWN, True),
    ],
)
@pytest.mark.usefixtures("init_components")
async def test_handle_intents_with_response_errors(
    hass: HomeAssistant,
    init_components: None,
    area_registry: ar.AreaRegistry,
    error_code: intent.IntentResponseErrorCode,
    return_response: bool,
) -> None:
    """Test that handle_intents does not return response errors."""
    assert await async_setup_component(hass, "climate", {})
    area_registry.async_create("living room")

    agent: default_agent.DefaultAgent = hass.data[DATA_DEFAULT_ENTITY]

    user_input = ConversationInput(
        text="What is the temperature in the living room?",
        context=Context(),
        conversation_id=None,
        device_id=None,
        language=hass.config.language,
        agent_id=None,
    )

    with patch(
        "homeassistant.components.conversation.default_agent.DefaultAgent._async_process_intent_result",
        return_value=default_agent._make_error_result(
            user_input.language, error_code, "Mock error message"
        ),
    ) as mock_process:
        response = await agent.async_handle_intents(user_input)

    assert len(mock_process.mock_calls) == 1

    if return_response:
        assert response is not None and response.error_code == error_code
    else:
        assert response is None


@pytest.mark.usefixtures("init_components")
async def test_handle_intents_filters_results(
    hass: HomeAssistant,
    init_components: None,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test that handle_intents can filter responses."""
    assert await async_setup_component(hass, "climate", {})
    area_registry.async_create("living room")

    agent: default_agent.DefaultAgent = hass.data[DATA_DEFAULT_ENTITY]

    user_input = ConversationInput(
        text="What is the temperature in the living room?",
        context=Context(),
        conversation_id=None,
        device_id=None,
        language=hass.config.language,
        agent_id=None,
    )

    mock_result = RecognizeResult(
        intent=Intent("HassTurnOn"),
        intent_data=IntentData([]),
        entities={},
        entities_list=[],
    )
    results = []

    def _filter_intents(result):
        results.append(result)
        # We filter first, not 2nd.
        return len(results) == 1

    with (
        patch(
            "homeassistant.components.conversation.default_agent.DefaultAgent.async_recognize_intent",
            return_value=mock_result,
        ) as mock_recognize,
        patch(
            "homeassistant.components.conversation.default_agent.DefaultAgent._async_process_intent_result",
        ) as mock_process,
    ):
        response = await agent.async_handle_intents(
            user_input, intent_filter=_filter_intents
        )

        assert len(mock_recognize.mock_calls) == 1
        assert len(mock_process.mock_calls) == 0

        # It was ignored
        assert response is None

        # Check we filtered things
        assert len(results) == 1
        assert results[0] is mock_result

        # Second time it is not filtered
        response = await agent.async_handle_intents(
            user_input, intent_filter=_filter_intents
        )

        assert len(mock_recognize.mock_calls) == 2
        assert len(mock_process.mock_calls) == 2

        # Check we filtered things
        assert len(results) == 2
        assert results[1] is mock_result

        # It was ignored
        assert response is not None


@pytest.mark.usefixtures("init_components")
async def test_state_names_are_not_translated(
    hass: HomeAssistant,
    init_components: None,
) -> None:
    """Test that state names are not translated in responses."""
    await async_setup_component(hass, "weather", {})

    hass.states.async_set("weather.test_weather", weather.ATTR_CONDITION_PARTLYCLOUDY)
    expose_entity(hass, "weather.test_weather", True)

    with patch(
        "homeassistant.helpers.template.Template.async_render"
    ) as mock_async_render:
        result = await conversation.async_converse(
            hass, "what is the weather like?", None, Context(), None
        )
        assert result.response.response_type == intent.IntentResponseType.QUERY_ANSWER
        mock_async_render.assert_called_once()

        assert (
            mock_async_render.call_args.args[0]["state"].state
            == weather.ATTR_CONDITION_PARTLYCLOUDY
        )


async def test_language_with_alternative_code(
    hass: HomeAssistant, init_components
) -> None:
    """Test different codes for the same language."""
    entity_ids: dict[str, str] = {}
    for i, (lang_code, sentence, name) in enumerate(
        (
            ("no", "slå på lampen", "lampen"),  # nb
            ("no-NO", "slå på lampen", "lampen"),  # nb
            ("iw", "הדליקי את המנורה", "מנורה"),  # he
        )
    ):
        if not (entity_id := entity_ids.get(name)):
            # Reuse entity id for the same name
            entity_id = f"light.test{i}"
            entity_ids[name] = entity_id

        hass.states.async_set(entity_id, "off", attributes={ATTR_FRIENDLY_NAME: name})
        calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
        await hass.services.async_call(
            "conversation",
            "process",
            {
                conversation.ATTR_TEXT: sentence,
                conversation.ATTR_LANGUAGE: lang_code,
            },
        )
        await hass.async_block_till_done()

        assert len(calls) == 1, f"Failed for {lang_code}, {sentence}"
        call = calls[0]
        assert call.domain == LIGHT_DOMAIN
        assert call.service == "turn_on"
        assert call.data == {"entity_id": [entity_id]}
