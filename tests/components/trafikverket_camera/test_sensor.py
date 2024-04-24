"""The test for the Trafikverket sensor platform."""
from __future__ import annotations

from pytrafikverket.trafikverket_camera import CameraInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_sensor(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    get_camera: CameraInfo,
) -> None:
    """Test the Trafikverket Camera sensor."""

    state = hass.states.get("sensor.test_location_direction")
    assert state.state == "180"
    state = hass.states.get("sensor.test_location_modified")
    assert state.state == "2022-04-04T04:04:04+00:00"
    state = hass.states.get("sensor.test_location_photo_time")
    assert state.state == "2022-04-04T04:04:04+00:00"
    state = hass.states.get("sensor.test_location_photo_url")
    assert state.state == "https://www.testurl.com/test_photo.jpg"
    state = hass.states.get("sensor.test_location_status")
    assert state.state == "Running"
    state = hass.states.get("sensor.test_location_camera_type")
    assert state.state == "Road"
