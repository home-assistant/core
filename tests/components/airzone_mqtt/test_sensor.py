"""The sensor tests for the Airzone platform."""

import pytest

from homeassistant.core import HomeAssistant

from .util import async_init_integration

from tests.typing import MqttMockHAClient


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_airzone_create_sensors(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test creation of sensors."""

    await async_init_integration(hass, mqtt_mock)

    # Zones
    state = hass.states.get("sensor.room_1_humidity")
    assert state.state == "35"

    state = hass.states.get("sensor.room_1_hvac_mode")
    assert state.state == "3"

    state = hass.states.get("sensor.room_1_hvac_maximum_setpoint")
    assert state.state == "30.0"

    state = hass.states.get("sensor.room_1_hvac_minimum_setpoint")
    assert state.state == "15.0"

    state = hass.states.get("sensor.room_1_hvac_setpoint")
    assert state.state == "20.5"

    state = hass.states.get("sensor.room_1_temperature")
    assert state.state == "21.9"

    state = hass.states.get("sensor.room_2_humidity")
    assert state.state == "44"

    state = hass.states.get("sensor.room_2_hvac_mode")
    assert state.state == "3"

    state = hass.states.get("sensor.room_2_hvac_setpoint")
    assert state.state == "21.5"

    state = hass.states.get("sensor.room_2_hvac_maximum_setpoint")
    assert state.state == "30.0"

    state = hass.states.get("sensor.room_2_hvac_minimum_setpoint")
    assert state.state == "15.0"

    state = hass.states.get("sensor.room_2_temperature")
    assert state.state == "22.6"
