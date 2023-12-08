"""The test for the Coolmaster binary sensor platform."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_binary_sensor(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster binary sensor."""
    assert hass.states.get("binary_sensor.l1_100_clean_filter").state == "off"
    assert hass.states.get("binary_sensor.l1_101_clean_filter").state == "on"
