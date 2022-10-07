"""The test for the Attribute as Sensor sensor platform."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant import config as hass_config
from homeassistant.components.attribute_as_sensor.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_RELOAD,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path


async def test_attribute_as_sensor(hass: HomeAssistant) -> None:
    """Test the sensor."""
    config = {
        "sensor": {
            "platform": "attribute_as_sensor",
            "name": "test_sensor",
            "entity_id": "sensor.test_1",
            "icon": "mdi:test-icon",
            "attribute": "test_attribute",
            "device_class": "temperature",
            "state_class": "measurement",
            "unit_of_measurement": "°C",
            "unique_id": "very_unique_id",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_id = config["sensor"]["entity_id"]
    hass.states.async_set(entity_id, 10, {"test_attribute": 20})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sensor")

    assert state.state == "20"
    assert state.attributes.get("entity_id") == "sensor.test_1"
    assert state.attributes.get(ATTR_ICON) == "mdi:test-icon"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS


async def test_attribute_as_sensor_missing_attribute(hass: HomeAssistant) -> None:
    """Test the sensor with faulty attribute."""
    config = {
        "sensor": {
            "platform": "attribute_as_sensor",
            "name": "test_sensor",
            "entity_id": "sensor.test_1",
            "icon": "mdi:test-icon",
            "attribute": "wrong_attribute",
            "device_class": "temperature",
            "state_class": "measurement",
            "unit_of_measurement": "°C",
            "unique_id": "very_unique_id",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_id = config["sensor"]["entity_id"]
    hass.states.async_set(entity_id, 10, {"test_attribute": 20})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sensor")

    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("entity_id") == "sensor.test_1"
    assert state.attributes.get(ATTR_ICON) == "mdi:test-icon"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS


async def test_reload(hass: HomeAssistant) -> None:
    """Verify we can reload filter sensors."""
    hass.states.async_set("sensor.test_1", 10, {"test_attribute": 20})

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "attribute_as_sensor",
                "name": "test_sensor",
                "entity_id": "sensor.test_1",
                "icon": "mdi:test-icon",
                "attribute": "test_attribute",
                "device_class": "temperature",
                "state_class": "measurement",
                "unit_of_measurement": "°C",
                "unique_id": "very_unique_id",
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test_sensor")

    yaml_path = get_fixture_path("configuration.yaml", "attribute_as_sensor")

    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    state = hass.states.get("sensor.test_sensor")
    assert state
    assert state.state == "20"
