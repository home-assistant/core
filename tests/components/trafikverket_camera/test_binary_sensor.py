"""The test for the Trafikverket binary sensor platform."""

from __future__ import annotations

from pytrafikverket.trafikverket_camera import CameraInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant


async def test_sensor(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    get_camera: CameraInfo,
) -> None:
    """Test the Trafikverket Camera binary sensor."""

    state = hass.states.get("binary_sensor.test_camera_active")
    assert state.state == STATE_ON
