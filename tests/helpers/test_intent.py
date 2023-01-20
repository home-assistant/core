"""Tests for the intent helpers."""

import pytest
import voluptuous as vol

from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import State
from homeassistant.helpers import (
    area_registry,
    config_validation as cv,
    entity_registry,
    intent,
)


class MockIntentHandler(intent.IntentHandler):
    """Provide a mock intent handler."""

    def __init__(self, slot_schema):
        """Initialize the mock handler."""
        self.slot_schema = slot_schema


async def test_async_match_states(hass):
    """Test async_match_state helper."""
    areas = area_registry.async_get(hass)
    area_kitchen = areas.async_get_or_create("kitchen")
    area_bedroom = areas.async_get_or_create("bedroom")

    state1 = State(
        "light.kitchen", "on", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )
    state2 = State(
        "switch.bedroom", "on", attributes={ATTR_FRIENDLY_NAME: "bedroom switch"}
    )

    # Put entities into different areas
    entities = entity_registry.async_get(hass)
    entities.async_get_or_create("light", "demo", "1234", suggested_object_id="kitchen")
    entities.async_update_entity(state1.entity_id, area_id=area_kitchen.id)

    entities.async_get_or_create(
        "switch", "demo", "1234", suggested_object_id="bedroom"
    )
    entities.async_update_entity(
        state2.entity_id,
        area_id=area_bedroom.id,
        device_class=SwitchDeviceClass.OUTLET,
        aliases={"kill switch"},
    )

    # Match on name
    assert [state1] == list(
        intent.async_match_states(hass, name="kitchen light", states=[state1, state2])
    )

    # Test alias
    assert [state2] == list(
        intent.async_match_states(hass, name="kill switch", states=[state1, state2])
    )

    # Name + area
    assert [state1] == list(
        intent.async_match_states(
            hass, name="kitchen light", area_name="kitchen", states=[state1, state2]
        )
    )

    # Wrong area
    assert not list(
        intent.async_match_states(
            hass, name="kitchen light", area_name="bedroom", states=[state1, state2]
        )
    )

    # Domain + area
    assert [state2] == list(
        intent.async_match_states(
            hass, domains={"switch"}, area_name="bedroom", states=[state1, state2]
        )
    )

    # Device class + area
    assert [state2] == list(
        intent.async_match_states(
            hass,
            device_classes={SwitchDeviceClass.OUTLET},
            area_name="bedroom",
            states=[state1, state2],
        )
    )


def test_async_validate_slots():
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
