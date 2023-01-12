"""Tests for the intent helpers."""

import pytest
import voluptuous as vol

from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import State
from homeassistant.helpers import config_validation as cv, entity_registry, intent


class MockIntentHandler(intent.IntentHandler):
    """Provide a mock intent handler."""

    def __init__(self, slot_schema):
        """Initialize the mock handler."""
        self.slot_schema = slot_schema


async def test_async_match_state(hass):
    """Test async_match_state helper."""
    state1 = State(
        "light.kitchen", "on", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )
    state2 = State(
        "switch.kitchen", "on", attributes={ATTR_FRIENDLY_NAME: "kitchen switch"}
    )
    registry = entity_registry.async_get(hass)
    registry.async_get_or_create(
        "switch", "demo", "1234", suggested_object_id="kitchen"
    )
    registry.async_update_entity(state2.entity_id, aliases={"kill switch"})

    state = intent.async_match_state(hass, "kitchen light", [state1, state2])
    assert state is state1

    state = intent.async_match_state(hass, "kill switch", [state1, state2])
    assert state is state2


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
