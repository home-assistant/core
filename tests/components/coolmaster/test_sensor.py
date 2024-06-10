"""The test for the Coolmaster sensor platform."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_sensor(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster sensor."""
    assert hass.states.get("sensor.l1_100_error_code").state == "OK"
    assert hass.states.get("sensor.l1_101_error_code").state == "Err1"
