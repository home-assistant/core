"""Test for the Abode sensor device."""
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

from .common import setup_platform


async def test_entity_registry(hass, requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, SENSOR_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get("sensor.environment_sensor_humidity")
    assert entry.unique_id == "13545b21f4bdcd33d9abd461f8443e65-humidity"


async def test_attributes(hass, requests_mock):
    """Test the sensor attributes are correct."""
    await setup_platform(hass, SENSOR_DOMAIN)

    state = hass.states.get("sensor.environment_sensor_humidity")
    assert state.state == "32.0"
    assert state.attributes.get("device_id") == "RF:02148e70"
    assert not state.attributes.get("battery_low")
    assert not state.attributes.get("no_response")
    assert state.attributes.get("device_type") == "LM"
    assert state.attributes.get("unit_of_measurement") == "%"
    assert state.attributes.get("friendly_name") == "Environment Sensor Humidity"
    assert state.attributes.get("device_class") == "humidity"

    state = hass.states.get("sensor.environment_sensor_lux")
    assert state.state == "1.0"
    assert state.attributes.get("unit_of_measurement") == "lux"

    state = hass.states.get("sensor.environment_sensor_temperature")
    # Abodepy device JSON reports 19.5, but Home Assistant shows 19.5
    assert state.state == "19.4"
    assert state.attributes.get("unit_of_measurement") == "°C"
