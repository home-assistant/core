"""Test for the default agent."""

from collections import defaultdict
from unittest.mock import AsyncMock, patch

from hassil.recognize import Intent, IntentData, MatchEntity, RecognizeResult
import pytest

from homeassistant.components import conversation
from homeassistant.components.conversation import default_agent
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
    floor_registry as fr,
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
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS


async def test_exposed_domains(hass: HomeAssistant, init_components) -> None:
    """Test that we can't interact with entities that aren't exposed."""
    hass.states.async_set(
        "media_player.test", "off", attributes={ATTR_FRIENDLY_NAME: "Test Media Player"}
    )

    result = await conversation.async_converse(
        hass, "turn on test media player", None, Context(), None
    )

    # This is a match failure instead of a handle failure because the media
    # player domain is not exposed.
    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS


async def test_exposed_areas(
    hass: HomeAssistant,
    init_components,
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


async def test_conversation_agent(
    hass: HomeAssistant,
    init_components,
) -> None:
    """Test DefaultAgent."""
    agent = default_agent.async_get_default_agent(hass)
    with patch(
        "homeassistant.components.conversation.default_agent.get_languages",
        return_value=["dwarvish", "elvish", "entish"],
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


async def test_unexposed_entities_skipped(
    hass: HomeAssistant,
    init_components,
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


async def test_trigger_sentences(hass: HomeAssistant, init_components) -> None:
    """Test registering/unregistering/matching a few trigger sentences."""
    trigger_sentences = ["It's party time", "It is time to party"]
    trigger_response = "Cowabunga!"

    agent = default_agent.async_get_default_agent(hass)
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


async def test_nevermind_item(hass: HomeAssistant, init_components) -> None:
    """Test HassNevermind intent through the default agent."""
    result = await conversation.async_converse(hass, "nevermind", None, Context())
    assert result.response.intent is not None
    assert result.response.intent.intent_type == intent.INTENT_NEVERMIND

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert not result.response.speech


async def test_device_area_context(
    hass: HomeAssistant,
    init_components,
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


async def test_error_no_device(hass: HomeAssistant, init_components) -> None:
    """Test error message when device/entity is missing."""
    result = await conversation.async_converse(
        hass, "turn on missing entity", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any device called missing entity"
    )


async def test_error_no_area(hass: HomeAssistant, init_components) -> None:
    """Test error message when area is missing."""
    result = await conversation.async_converse(
        hass, "turn on the lights in missing area", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any area called missing area"
    )


async def test_error_no_floor(hass: HomeAssistant, init_components) -> None:
    """Test error message when floor is missing."""
    result = await conversation.async_converse(
        hass, "turn on all the lights on missing floor", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any floor called missing"
    )


async def test_error_no_device_in_area(
    hass: HomeAssistant, init_components, area_registry: ar.AreaRegistry
) -> None:
    """Test error message when area is missing a device/entity."""
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


async def test_error_no_domain(
    hass: HomeAssistant, init_components, area_registry: ar.AreaRegistry
) -> None:
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
        "homeassistant.components.conversation.default_agent.recognize_all",
        return_value=[recognize_result],
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


async def test_error_no_domain_in_area(
    hass: HomeAssistant, init_components, area_registry: ar.AreaRegistry
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


async def test_error_no_domain_in_floor(
    hass: HomeAssistant,
    init_components,
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


async def test_error_no_device_class(hass: HomeAssistant, init_components) -> None:
    """Test error message when no entities of a device class exist."""

    # We don't have a sentence for opening all windows
    window_class = MatchEntity(name="device_class", value="window", text="windows")
    recognize_result = RecognizeResult(
        intent=Intent("HassTurnOn"),
        intent_data=IntentData([]),
        entities={"device_class": window_class},
        entities_list=[window_class],
    )

    with patch(
        "homeassistant.components.conversation.default_agent.recognize_all",
        return_value=[recognize_result],
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


async def test_error_no_device_class_in_area(
    hass: HomeAssistant, init_components, area_registry: ar.AreaRegistry
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


async def test_error_no_intent(hass: HomeAssistant, init_components) -> None:
    """Test response with an intent match failure."""
    with patch(
        "homeassistant.components.conversation.default_agent.recognize_all",
        return_value=[],
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


async def test_error_duplicate_names(
    hass: HomeAssistant, init_components, entity_registry: er.EntityRegistry
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


async def test_error_duplicate_names_in_area(
    hass: HomeAssistant,
    init_components,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test error message when multiple devices have the same name (or alias)."""
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


async def test_no_states_matched_default_error(
    hass: HomeAssistant, init_components, area_registry: ar.AreaRegistry
) -> None:
    """Test default response when no states match and slots are missing."""
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(area_kitchen.id, name="kitchen")

    with patch(
        "homeassistant.components.conversation.default_agent.intent.async_handle",
        side_effect=intent.NoStatesMatchedError(),
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


async def test_empty_aliases(
    hass: HomeAssistant,
    init_components,
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
            hass, "turn on lights in the kitchen", None, Context(), None
        )

        assert mock_recognize_all.call_count > 0
        slot_lists = mock_recognize_all.call_args[0][2]

        # Slot lists should only contain non-empty text
        assert slot_lists.keys() == {"area", "name", "floor"}
        areas = slot_lists["area"]
        assert len(areas.values) == 1
        assert areas.values[0].value_out == area_kitchen.id
        assert areas.values[0].text_in.text == area_kitchen.normalized_name

        names = slot_lists["name"]
        assert len(names.values) == 1
        assert names.values[0].value_out == kitchen_light.name
        assert names.values[0].text_in.text == kitchen_light.name

        floors = slot_lists["floor"]
        assert len(floors.values) == 1
        assert floors.values[0].value_out == floor_1.floor_id
        assert floors.values[0].text_in.text == floor_1.name


async def test_all_domains_loaded(hass: HomeAssistant, init_components) -> None:
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


async def test_same_named_entities_in_different_areas(
    hass: HomeAssistant,
    init_components,
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


async def test_same_aliased_entities_in_different_areas(
    hass: HomeAssistant,
    init_components,
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
