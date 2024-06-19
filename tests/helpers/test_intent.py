"""Tests for the intent helpers."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components import conversation, light, switch
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
)
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    intent,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_mock_service


class MockIntentHandler(intent.IntentHandler):
    """Provide a mock intent handler."""

    def __init__(self, slot_schema) -> None:
        """Initialize the mock handler."""
        self._mock_slot_schema = slot_schema

    @property
    def slot_schema(self):
        """Return the slot schema."""
        return self._mock_slot_schema


async def test_async_match_states(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test async_match_state helper."""
    area_kitchen = area_registry.async_get_or_create("kitchen")
    area_kitchen = area_registry.async_update(area_kitchen.id, aliases={"food room"})
    area_bedroom = area_registry.async_get_or_create("bedroom")

    # Kitchen is on the first floor
    floor_1 = floor_registry.async_create("first floor", aliases={"ground floor"})
    area_kitchen = area_registry.async_update(
        area_kitchen.id, floor_id=floor_1.floor_id
    )

    # Bedroom is on the second floor
    floor_2 = floor_registry.async_create("second floor")
    area_bedroom = area_registry.async_update(
        area_bedroom.id, floor_id=floor_2.floor_id
    )

    state1 = State(
        "light.kitchen", "on", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )
    state2 = State(
        "switch.bedroom", "on", attributes={ATTR_FRIENDLY_NAME: "bedroom switch"}
    )

    # Put entities into different areas
    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="kitchen"
    )
    entity_registry.async_update_entity(state1.entity_id, area_id=area_kitchen.id)

    entity_registry.async_get_or_create(
        "switch", "demo", "5678", suggested_object_id="bedroom"
    )
    entity_registry.async_update_entity(
        state2.entity_id,
        area_id=area_bedroom.id,
        device_class=switch.SwitchDeviceClass.OUTLET,
        aliases={"kill switch"},
    )

    # Match on name
    assert list(
        intent.async_match_states(hass, name="kitchen light", states=[state1, state2])
    ) == [state1]

    # Test alias
    assert list(
        intent.async_match_states(hass, name="kill switch", states=[state1, state2])
    ) == [state2]

    # Name + area
    assert list(
        intent.async_match_states(
            hass, name="kitchen light", area_name="kitchen", states=[state1, state2]
        )
    ) == [state1]

    # Test area alias
    assert list(
        intent.async_match_states(
            hass, name="kitchen light", area_name="food room", states=[state1, state2]
        )
    ) == [state1]

    # Wrong area
    assert not list(
        intent.async_match_states(
            hass, name="kitchen light", area_name="bedroom", states=[state1, state2]
        )
    )

    # Invalid area
    assert not list(
        intent.async_match_states(
            hass, area_name="invalid area", states=[state1, state2]
        )
    )

    # Domain + area
    assert list(
        intent.async_match_states(
            hass, domains={"switch"}, area_name="bedroom", states=[state1, state2]
        )
    ) == [state2]

    # Device class + area
    assert list(
        intent.async_match_states(
            hass,
            device_classes={switch.SwitchDeviceClass.OUTLET},
            area_name="bedroom",
            states=[state1, state2],
        )
    ) == [state2]

    # Floor
    assert list(
        intent.async_match_states(
            hass, floor_name="first floor", states=[state1, state2]
        )
    ) == [state1]

    assert list(
        intent.async_match_states(
            # Check alias
            hass,
            floor_name="ground floor",
            states=[state1, state2],
        )
    ) == [state1]

    assert list(
        intent.async_match_states(
            hass, floor_name="second floor", states=[state1, state2]
        )
    ) == [state2]

    # Invalid floor
    assert not list(
        intent.async_match_states(
            hass, floor_name="invalid floor", states=[state1, state2]
        )
    )


async def test_async_match_targets(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Tests for async_match_targets function."""
    # Needed for exposure
    assert await async_setup_component(hass, "homeassistant", {})

    # House layout
    # Floor 1 (ground):
    #   - Kitchen
    #     - Outlet
    #   - Bathroom
    #     - Light
    # Floor 2 (upstairs)
    #   - Bedroom
    #     - Switch
    #   - Bathroom
    #     - Light
    # Floor 3 (also upstairs)
    #   - Bedroom
    #     - Switch
    #   - Bathroom
    #     - Light

    # Floor 1
    floor_1 = floor_registry.async_create("first floor", aliases={"ground"})
    area_kitchen = area_registry.async_get_or_create("kitchen")
    area_kitchen = area_registry.async_update(
        area_kitchen.id, floor_id=floor_1.floor_id
    )
    area_bathroom_1 = area_registry.async_get_or_create("first floor bathroom")
    area_bathroom_1 = area_registry.async_update(
        area_bathroom_1.id, aliases={"bathroom"}, floor_id=floor_1.floor_id
    )

    kitchen_outlet = entity_registry.async_get_or_create(
        "switch", "test", "kitchen_outlet"
    )
    kitchen_outlet = entity_registry.async_update_entity(
        kitchen_outlet.entity_id,
        name="kitchen outlet",
        device_class=switch.SwitchDeviceClass.OUTLET,
        area_id=area_kitchen.id,
    )
    state_kitchen_outlet = State(kitchen_outlet.entity_id, "on")

    bathroom_light_1 = entity_registry.async_get_or_create(
        "light", "test", "bathroom_light_1"
    )
    bathroom_light_1 = entity_registry.async_update_entity(
        bathroom_light_1.entity_id,
        name="bathroom light",
        aliases={"overhead light"},
        area_id=area_bathroom_1.id,
    )
    state_bathroom_light_1 = State(bathroom_light_1.entity_id, "off")

    # Floor 2
    floor_2 = floor_registry.async_create("second floor", aliases={"upstairs"})
    area_bedroom_2 = area_registry.async_get_or_create("bedroom")
    area_bedroom_2 = area_registry.async_update(
        area_bedroom_2.id, floor_id=floor_2.floor_id
    )
    area_bathroom_2 = area_registry.async_get_or_create("second floor bathroom")
    area_bathroom_2 = area_registry.async_update(
        area_bathroom_2.id, aliases={"bathroom"}, floor_id=floor_2.floor_id
    )

    bedroom_switch_2 = entity_registry.async_get_or_create(
        "switch", "test", "bedroom_switch_2"
    )
    bedroom_switch_2 = entity_registry.async_update_entity(
        bedroom_switch_2.entity_id,
        name="second floor bedroom switch",
        area_id=area_bedroom_2.id,
    )
    state_bedroom_switch_2 = State(
        bedroom_switch_2.entity_id,
        "off",
    )

    bathroom_light_2 = entity_registry.async_get_or_create(
        "light", "test", "bathroom_light_2"
    )
    bathroom_light_2 = entity_registry.async_update_entity(
        bathroom_light_2.entity_id,
        aliases={"bathroom light", "overhead light"},
        area_id=area_bathroom_2.id,
        supported_features=light.LightEntityFeature.EFFECT,
    )
    state_bathroom_light_2 = State(bathroom_light_2.entity_id, "off")

    # Floor 3
    floor_3 = floor_registry.async_create("third floor", aliases={"upstairs"})
    area_bedroom_3 = area_registry.async_get_or_create("bedroom")
    area_bedroom_3 = area_registry.async_update(
        area_bedroom_3.id, floor_id=floor_3.floor_id
    )
    area_bathroom_3 = area_registry.async_get_or_create("third floor bathroom")
    area_bathroom_3 = area_registry.async_update(
        area_bathroom_3.id, aliases={"bathroom"}, floor_id=floor_3.floor_id
    )

    bedroom_switch_3 = entity_registry.async_get_or_create(
        "switch", "test", "bedroom_switch_3"
    )
    bedroom_switch_3 = entity_registry.async_update_entity(
        bedroom_switch_3.entity_id,
        name="third floor bedroom switch",
        area_id=area_bedroom_3.id,
    )
    state_bedroom_switch_3 = State(
        bedroom_switch_3.entity_id,
        "off",
        attributes={ATTR_DEVICE_CLASS: switch.SwitchDeviceClass.OUTLET},
    )

    bathroom_light_3 = entity_registry.async_get_or_create(
        "light", "test", "bathroom_light_3"
    )
    bathroom_light_3 = entity_registry.async_update_entity(
        bathroom_light_3.entity_id,
        name="overhead light",
        area_id=area_bathroom_3.id,
    )
    state_bathroom_light_3 = State(
        bathroom_light_3.entity_id,
        "on",
        attributes={
            ATTR_FRIENDLY_NAME: "bathroom light",
            ATTR_SUPPORTED_FEATURES: light.LightEntityFeature.EFFECT,
        },
    )

    # -----
    bathroom_light_states = [
        state_bathroom_light_1,
        state_bathroom_light_2,
        state_bathroom_light_3,
    ]
    states = [
        *bathroom_light_states,
        state_kitchen_outlet,
        state_bedroom_switch_2,
        state_bedroom_switch_3,
    ]

    # Not a unique name
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(name="bathroom light"),
        states=states,
    )
    assert not result.is_match
    assert result.no_match_reason == intent.MatchFailedReason.DUPLICATE_NAME
    assert result.no_match_name == "bathroom light"

    # Works with duplicate names allowed
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(
            name="bathroom light", allow_duplicate_names=True
        ),
        states=states,
    )
    assert result.is_match
    assert {s.entity_id for s in result.states} == {
        s.entity_id for s in bathroom_light_states
    }

    # Also works when name is not a constraint
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(domains={"light"}),
        states=states,
    )
    assert result.is_match
    assert {s.entity_id for s in result.states} == {
        s.entity_id for s in bathroom_light_states
    }

    # We can disambiguate by preferred floor (from context)
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(name="bathroom light"),
        intent.MatchTargetsPreferences(floor_id=floor_3.floor_id),
        states=states,
    )
    assert result.is_match
    assert len(result.states) == 1
    assert result.states[0].entity_id == bathroom_light_3.entity_id

    # Also disambiguate by preferred area (from context)
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(name="bathroom light"),
        intent.MatchTargetsPreferences(area_id=area_bathroom_2.id),
        states=states,
    )
    assert result.is_match
    assert len(result.states) == 1
    assert result.states[0].entity_id == bathroom_light_2.entity_id

    # Disambiguate by floor name, if unique
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(name="bathroom light", floor_name="ground"),
        states=states,
    )
    assert result.is_match
    assert len(result.states) == 1
    assert result.states[0].entity_id == bathroom_light_1.entity_id

    # Doesn't work if floor name/alias is not unique
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(name="bathroom light", floor_name="upstairs"),
        states=states,
    )
    assert not result.is_match
    assert result.no_match_reason == intent.MatchFailedReason.DUPLICATE_NAME

    # Disambiguate by area name, if unique
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(
            name="bathroom light", area_name="first floor bathroom"
        ),
        states=states,
    )
    assert result.is_match
    assert len(result.states) == 1
    assert result.states[0].entity_id == bathroom_light_1.entity_id

    # Doesn't work if area name/alias is not unique
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(name="bathroom light", area_name="bathroom"),
        states=states,
    )
    assert not result.is_match
    assert result.no_match_reason == intent.MatchFailedReason.DUPLICATE_NAME

    # Does work if floor/area name combo is unique
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(
            name="bathroom light", area_name="bathroom", floor_name="ground"
        ),
        states=states,
    )
    assert result.is_match
    assert len(result.states) == 1
    assert result.states[0].entity_id == bathroom_light_1.entity_id

    # Doesn't work if area is not part of the floor
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(
            name="bathroom light",
            area_name="second floor bathroom",
            floor_name="ground",
        ),
        states=states,
    )
    assert not result.is_match
    assert result.no_match_reason == intent.MatchFailedReason.AREA

    # Check state constraint (only third floor bathroom light is on)
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(domains={"light"}, states={"on"}),
        states=states,
    )
    assert result.is_match
    assert len(result.states) == 1
    assert result.states[0].entity_id == bathroom_light_3.entity_id

    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(
            domains={"light"}, states={"on"}, floor_name="ground"
        ),
        states=states,
    )
    assert not result.is_match

    # Check assistant constraint (exposure)
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(assistant="test"),
        states=states,
    )
    assert not result.is_match

    async_expose_entity(hass, "test", bathroom_light_1.entity_id, True)
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(assistant="test"),
        states=states,
    )
    assert result.is_match
    assert len(result.states) == 1
    assert result.states[0].entity_id == bathroom_light_1.entity_id

    # Check device class constraint
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(
            domains={"switch"}, device_classes={switch.SwitchDeviceClass.OUTLET}
        ),
        states=states,
    )
    assert result.is_match
    assert len(result.states) == 2
    assert {s.entity_id for s in result.states} == {
        kitchen_outlet.entity_id,
        bedroom_switch_3.entity_id,
    }

    # Check features constraint (second and third floor bathroom lights have effects)
    result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(
            domains={"light"}, features=light.LightEntityFeature.EFFECT
        ),
        states=states,
    )
    assert result.is_match
    assert len(result.states) == 2
    assert {s.entity_id for s in result.states} == {
        bathroom_light_2.entity_id,
        bathroom_light_3.entity_id,
    }


async def test_match_device_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test async_match_state with a device in an area."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    area_kitchen = area_registry.async_get_or_create("kitchen")
    area_bedroom = area_registry.async_get_or_create("bedroom")

    kitchen_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections=set(),
        identifiers={("demo", "id-1234")},
    )
    device_registry.async_update_device(kitchen_device.id, area_id=area_kitchen.id)

    state1 = State(
        "light.kitchen", "on", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )
    state2 = State(
        "light.bedroom", "on", attributes={ATTR_FRIENDLY_NAME: "bedroom light"}
    )
    state3 = State(
        "light.living_room", "on", attributes={ATTR_FRIENDLY_NAME: "living room light"}
    )
    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="kitchen"
    )
    entity_registry.async_update_entity(state1.entity_id, device_id=kitchen_device.id)

    entity_registry.async_get_or_create(
        "light", "demo", "5678", suggested_object_id="bedroom"
    )
    entity_registry.async_update_entity(state2.entity_id, area_id=area_bedroom.id)

    # Match on area/domain
    assert list(
        intent.async_match_states(
            hass,
            domains={"light"},
            area_name="kitchen",
            states=[state1, state2, state3],
        )
    ) == [state1]


def test_async_validate_slots() -> None:
    """Test async_validate_slots of IntentHandler."""
    handler1 = MockIntentHandler({vol.Required("name"): cv.string})

    with pytest.raises(vol.error.MultipleInvalid):
        handler1.async_validate_slots({})
    with pytest.raises(vol.error.MultipleInvalid):
        handler1.async_validate_slots({"name": 1})
    with pytest.raises(vol.error.MultipleInvalid):
        handler1.async_validate_slots({"name": "kitchen"})
    handler1.async_validate_slots({"name": {"value": "kitchen"}})
    handler1.async_validate_slots(
        {"name": {"value": "kitchen"}, "probability": {"value": "0.5"}}
    )


def test_async_validate_slots_no_schema() -> None:
    """Test async_validate_slots of IntentHandler with no schema."""
    handler1 = MockIntentHandler(None)
    assert handler1.async_validate_slots({"name": {"value": "kitchen"}}) == {
        "name": {"value": "kitchen"}
    }


async def test_cant_turn_on_lock(hass: HomeAssistant) -> None:
    """Test that we can't turn on entities that don't support it."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "lock", {})

    hass.states.async_set(
        "lock.test", "123", attributes={ATTR_FRIENDLY_NAME: "Test Lock"}
    )

    result = await conversation.async_converse(
        hass, "turn on test lock", None, Context(), None
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_VALID_TARGETS


def test_async_register(hass: HomeAssistant) -> None:
    """Test registering an intent and verifying it is stored correctly."""
    handler = MagicMock()
    handler.intent_type = "test_intent"

    intent.async_register(hass, handler)

    assert list(intent.async_get(hass)) == [handler]


def test_async_register_overwrite(hass: HomeAssistant) -> None:
    """Test registering multiple intents with the same type, ensuring the last one overwrites the previous one and a warning is emitted."""
    handler1 = MagicMock()
    handler1.intent_type = "test_intent"

    handler2 = MagicMock()
    handler2.intent_type = "test_intent"

    with patch.object(intent._LOGGER, "warning") as mock_warning:
        intent.async_register(hass, handler1)
        intent.async_register(hass, handler2)

        mock_warning.assert_called_once_with(
            "Intent %s is being overwritten by %s", "test_intent", handler2
        )

    assert list(intent.async_get(hass)) == [handler2]


def test_async_remove(hass: HomeAssistant) -> None:
    """Test removing an intent and verifying it is no longer present in the Home Assistant data."""
    handler = MagicMock()
    handler.intent_type = "test_intent"

    intent.async_register(hass, handler)
    intent.async_remove(hass, "test_intent")

    assert not list(intent.async_get(hass))


def test_async_remove_no_existing_entry(hass: HomeAssistant) -> None:
    """Test the removal of a non-existing intent from Home Assistant's data."""
    handler = MagicMock()
    handler.intent_type = "test_intent"
    intent.async_register(hass, handler)

    intent.async_remove(hass, "test_intent2")

    assert list(intent.async_get(hass)) == [handler]


def test_async_remove_no_existing(hass: HomeAssistant) -> None:
    """Test the removal of an intent where no config exists."""

    intent.async_remove(hass, "test_intent2")
    # simply shouldn't cause an exception

    assert intent.DATA_KEY not in hass.data


async def test_validate_then_run_in_background(hass: HomeAssistant) -> None:
    """Test we don't execute a service in foreground forever."""
    hass.states.async_set("light.kitchen", "off")
    call_done = asyncio.Event()
    calls = []

    # Register a service that takes 0.1 seconds to execute
    async def mock_service(call):
        """Mock service."""
        await asyncio.sleep(0.1)
        call_done.set()
        calls.append(call)

    hass.services.async_register("light", "turn_on", mock_service)

    # Create intent handler with a service timeout of 0.05 seconds
    handler = intent.ServiceIntentHandler(
        "TestType", "light", "turn_on", "Turned {} on"
    )
    handler.service_timeout = 0.05
    intent.async_register(hass, handler)

    result = await intent.async_handle(
        hass,
        "test",
        "TestType",
        slots={"name": {"value": "kitchen"}},
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    assert not call_done.is_set()
    await call_done.wait()

    assert len(calls) == 1
    assert calls[0].data == {"entity_id": "light.kitchen"}


async def test_invalid_area_floor_names(hass: HomeAssistant) -> None:
    """Test that we throw an appropriate errors with invalid area/floor names."""
    handler = intent.ServiceIntentHandler(
        "TestType", "light", "turn_on", "Turned {} on"
    )
    intent.async_register(hass, handler)

    # Need a light to avoid domain error
    hass.states.async_set("light.test", "off")

    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            "TestType",
            slots={"area": {"value": "invalid area"}},
        )
    assert err.value.result.no_match_reason == intent.MatchFailedReason.INVALID_AREA

    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            "TestType",
            slots={"floor": {"value": "invalid floor"}},
        )
    assert err.value.result.no_match_reason == intent.MatchFailedReason.INVALID_FLOOR


async def test_service_intent_handler_required_domains(hass: HomeAssistant) -> None:
    """Test that required_domains restricts the domain of a ServiceIntentHandler."""
    hass.states.async_set("light.kitchen", "off")
    hass.states.async_set("switch.bedroom", "off")

    calls = async_mock_service(hass, "homeassistant", "turn_on")
    handler = intent.ServiceIntentHandler(
        "TestType",
        "homeassistant",
        "turn_on",
        "Turned {} on",
        required_domains={"light"},
    )
    intent.async_register(hass, handler)

    # Should work fine
    result = await intent.async_handle(
        hass,
        "test",
        "TestType",
        slots={"name": {"value": "kitchen"}, "domain": {"value": "light"}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1

    # Fails because the intent handler is restricted to lights only
    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            "TestType",
            slots={"name": {"value": "bedroom"}},
        )

    # Still fails even if we provide the domain
    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            "TestType",
            slots={"name": {"value": "bedroom"}, "domain": {"value": "switch"}},
        )


async def test_service_handler_empty_strings(hass: HomeAssistant) -> None:
    """Test that passing empty strings for filters fails in ServiceIntentHandler."""
    handler = intent.ServiceIntentHandler(
        "TestType", "light", "turn_on", "Turned {} on"
    )
    intent.async_register(hass, handler)

    for slot_name in ("name", "area", "floor"):
        # Empty string
        with pytest.raises(intent.InvalidSlotInfo):
            await intent.async_handle(
                hass,
                "test",
                "TestType",
                slots={slot_name: {"value": ""}},
            )

        # Whitespace
        with pytest.raises(intent.InvalidSlotInfo):
            await intent.async_handle(
                hass,
                "test",
                "TestType",
                slots={slot_name: {"value": "  "}},
            )


async def test_service_handler_no_filter(hass: HomeAssistant) -> None:
    """Test that targeting all devices in the house fails."""
    handler = intent.ServiceIntentHandler(
        "TestType", "light", "turn_on", "Turned {} on"
    )
    intent.async_register(hass, handler)

    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(
            hass,
            "test",
            "TestType",
        )
