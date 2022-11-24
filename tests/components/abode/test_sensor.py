"""Tests for the Abode sensor device."""
from spencerassistant.components.abode import ATTR_DEVICE_ID
from spencerassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from spencerassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from spencerassistant.core import spencerAssistant
from spencerassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_entity_registry(hass: spencerAssistant) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, SENSOR_DOMAIN)
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("sensor.environment_sensor_humidity")
    assert entry.unique_id == "13545b21f4bdcd33d9abd461f8443e65-humidity"


async def test_attributes(hass: spencerAssistant) -> None:
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
    # Abodepy device JSON reports 19.5, but spencer Assistant shows 19.4
    assert state.state == "19.4"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS
