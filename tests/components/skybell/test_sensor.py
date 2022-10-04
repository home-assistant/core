"""Sensor tests for the Skybell integration."""
from unittest.mock import AsyncMock

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant

from .conftest import async_init_integration


async def test_sensors(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: AsyncMock,
    connection,
) -> None:
    """Test we get sensor data."""
    await async_init_integration(hass)

    state = hass.states.get("sensor.front_door_chime_level")
    assert state.state == "1"
    state = hass.states.get("sensor.front_door_last_button_event")
    assert state.state == "1970-01-01T00:00:00+00:00"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    state = hass.states.get("sensor.front_door_last_motion_event")
    assert state.state == "2020-03-30T12:35:02+00:00"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    state = hass.states.get("sensor.front_door_last_check_in")
    assert state.state == "2020-03-31T04:13:37+00:00"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    state = hass.states.get("sensor.front_door_motion_threshold")
    assert state.state == "32"
    state = hass.states.get("sensor.front_door_video_profile")
    assert state.state == "1"
    state = hass.states.get("sensor.front_door_wifi_ssid")
    assert state.state == "wifi"
    state = hass.states.get("sensor.front_door_wifi_status")
    assert state.state == "poor"
