"""Tests for VeSync air purifiers."""

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    FanEntityFeature,
)
from homeassistant.components.humidifier import MODE_AUTO, MODE_SLEEP
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_SUPPORTED_FEATURES, STATE_ON


async def test_attributes_air_purifier(hass, setup_platform):
    """Test the air purifier attributes are correct."""
    state = hass.states.get("fan.air_purifier_400s")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_PERCENTAGE) == 25
    assert state.attributes.get(ATTR_PERCENTAGE_STEP) == 25
    assert state.attributes.get(ATTR_PRESET_MODE) is None
    assert state.attributes.get(ATTR_PRESET_MODES) == [
        MODE_AUTO,
        MODE_SLEEP,
    ]
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Air Purifier 400s"
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == FanEntityFeature.SET_SPEED
