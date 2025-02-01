"""The test for the Trafikverket sensor platform."""

from __future__ import annotations

import pytest
from pytrafikverket import CameraInfoModel

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    get_camera: CameraInfoModel,
) -> None:
    """Test the Trafikverket Camera sensor."""

    state = hass.states.get("sensor.test_camera_direction")
    assert state.state == "180"
    state = hass.states.get("sensor.test_camera_modified")
    assert state.state == "2022-04-04T04:04:04+00:00"
    state = hass.states.get("sensor.test_camera_photo_time")
    assert state.state == "2022-04-04T04:04:04+00:00"
    state = hass.states.get("sensor.test_camera_photo_url")
    assert state.state == "https://www.testurl.com/test_photo.jpg"
    state = hass.states.get("sensor.test_camera_status")
    assert state.state == "Running"
    state = hass.states.get("sensor.test_camera_camera_type")
    assert state.state == "Road"
