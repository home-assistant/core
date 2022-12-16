"""Tests for VeSync humidifiers."""

from homeassistant.components.humidifier import (
    ATTR_AVAILABLE_MODES,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    MODE_AUTO,
    MODE_NORMAL,
    MODE_SLEEP,
    HumidifierDeviceClass,
    HumidifierEntityFeature,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    STATE_ON,
)


async def test_attributes_humidifier(hass, setup_platform):
    """Test the humidifier attributes are correct."""
    state = hass.states.get("humidifier.humidifier_300s")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_MIN_HUMIDITY) == 30
    assert state.attributes.get(ATTR_MAX_HUMIDITY) == 80
    assert state.attributes.get(ATTR_HUMIDITY) == 40
    assert state.attributes.get(ATTR_AVAILABLE_MODES) == [
        MODE_NORMAL,
        MODE_AUTO,
        MODE_SLEEP,
    ]
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Humidifier 300s"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == HumidifierDeviceClass.HUMIDIFIER
    assert (
        state.attributes.get(ATTR_SUPPORTED_FEATURES) == HumidifierEntityFeature.MODES
    )
