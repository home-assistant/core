"""Test Snoo Sensors."""

from homeassistant.core import HomeAssistant

from . import async_init_integration
from .conftest import MockedSnoo


async def test_sensors(hass: HomeAssistant, bypass_api: MockedSnoo) -> None:
    """Test sensors and check test values are correctly set."""
    await async_init_integration(hass)

    assert len(hass.states.async_all("sensor")) == 2
    assert hass.states.get("sensor.test_snoo_state").state == "stop"
    assert hass.states.get("sensor.test_snoo_time_left").state == "unknown"
