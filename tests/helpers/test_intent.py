"""Tests for the intent helpers."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    intent,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


class MockIntentHandler(intent.IntentHandler):
    """Provide a mock intent handler."""

    def __init__(self, slot_schema):
        """Initialize the mock handler."""
        self.slot_schema = slot_schema


async def test_async_match_states(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test async_match_state helper."""
    area_kitchen = area_registry.async_get_or_create("kitchen")
    area_registry.async_update(area_kitchen.id, aliases={"food room"})
    area_bedroom = area_registry.async_get_or_create("bedroom")

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
        device_class=SwitchDeviceClass.OUTLET,
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
            device_classes={SwitchDeviceClass.OUTLET},
            area_name="bedroom",
            states=[state1, state2],
        )
    ) == [state2]


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
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_INTENT_MATCH


def test_async_register(hass: HomeAssistant) -> None:
    """Test registering an intent and verifying it is stored correctly."""
    handler = MagicMock()
    handler.intent_type = "test_intent"

    intent.async_register(hass, handler)

    assert hass.data[intent.DATA_KEY]["test_intent"] == handler


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

    assert hass.data[intent.DATA_KEY]["test_intent"] == handler2


def test_async_remove(hass: HomeAssistant) -> None:
    """Test removing an intent and verifying it is no longer present in the Home Assistant data."""
    handler = MagicMock()
    handler.intent_type = "test_intent"

    intent.async_register(hass, handler)
    intent.async_remove(hass, "test_intent")

    assert "test_intent" not in hass.data[intent.DATA_KEY]


def test_async_remove_no_existing_entry(hass: HomeAssistant) -> None:
    """Test the removal of a non-existing intent from Home Assistant's data."""
    handler = MagicMock()
    handler.intent_type = "test_intent"
    intent.async_register(hass, handler)

    intent.async_remove(hass, "test_intent2")

    assert "test_intent2" not in hass.data[intent.DATA_KEY]


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
