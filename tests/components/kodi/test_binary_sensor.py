"""Tests for Kodi binary sensors."""

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_screensaver_binary_sensor_defaults_off(hass: HomeAssistant) -> None:
    """Test the Kodi screensaver binary sensor is created."""
    await init_integration(hass)

    state = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.name_screensaver")

    assert state is not None
    assert state.state == "off"


async def test_screensaver_binary_sensor_can_be_on(hass: HomeAssistant) -> None:
    """Test the Kodi screensaver binary sensor reports the Kodi state."""
    await init_integration(
        hass,
        call_method_return_value={"System.ScreenSaverActive": True},
    )

    state = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.name_screensaver")

    assert state is not None
    assert state.state == "on"
