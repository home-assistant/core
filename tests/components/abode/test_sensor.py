"""Tests for the Abode sensor device."""
from homeassistant.components.abode import ATTR_DEVICE_ID
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_entity_registry(hass: HomeAssistant) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, SENSOR_DOMAIN)
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("sensor.environment_sensor_humidity")
    assert entry.unique_id == "13545b21f4bdcd33d9abd461f8443e65-humidity"


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the sensor attributes are correct."""
    await setup_platform(hass, SENSOR_DOMAIN)

    state = hass.states.get("sensor.environment_sensor_humidity")
    assert state.state == "32.0"
    assert state.attributes.get(ATTR_DEVICE_ID) == "RF:02148e70"
    assert not state.attributes.get("battery_low")
    assert not state.attributes.get("no_response")
    assert state.attributes.get("device_type") == "LM"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Environment Sensor Humidity"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.HUMIDITY

    state = hass.states.get("sensor.environment_sensor_lux")
    assert state.state == "1.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "lux"

    state = hass.states.get("sensor.environment_sensor_temperature")
    # Abodepy device JSON reports 19.5, but Home Assistant shows 19.4
    assert state.state == "19.4"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS
