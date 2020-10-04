"""Tests for 1-Wire temperature sensor (device family 10, 22, 28, 3B, 42) connected on SysBus."""
from os import path
from unittest.mock import PropertyMock, patch

from pi1wire import (
    InvalidCRCException,
    NotFoundSensorException,
    UnsupportResponseException,
)

from homeassistant.components.onewire.const import DEFAULT_SYSBUS_MOUNT_DIR, DOMAIN
from homeassistant.components.onewire.sensor import OneWireDirect
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import TEMP_CELSIUS
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from tests.common import mock_registry

MOCK_DEVICE_ID = "28-111111111111"
MOCK_DEVICE_NAME = "My DS18B20"


async def test_onewiredirect_setup(hass):
    """Test that sysbus config entry works correctly."""
    entity_registry = mock_registry(hass)
    config = {
        "sensor": {
            "platform": DOMAIN,
            "names": {
                MOCK_DEVICE_ID: MOCK_DEVICE_NAME,
            },
        }
    }
    with patch(
        "homeassistant.components.onewire.sensor.Pi1Wire"
    ) as mock_pi1wire, patch("pi1wire.OneWire") as mock_owsensor:
        type(mock_owsensor).mac_address = PropertyMock(
            return_value=MOCK_DEVICE_ID.replace("-", "")
        )
        mock_owsensor.get_temperature.return_value = "25.123"
        mock_pi1wire.return_value.find_all_sensors.return_value = [mock_owsensor]
        assert await async_setup_component(hass, SENSOR_DOMAIN, config)
        await hass.async_block_till_done()

        assert len(entity_registry.entities) == 1
        sensor_id = "sensor." + slugify(MOCK_DEVICE_NAME) + "_temperature"
        sensor_entity = entity_registry.entities.get(sensor_id)
        assert sensor_entity is not None
        assert (
            sensor_entity.unique_id == f"/sys/bus/w1/devices/{MOCK_DEVICE_ID}/w1_slave"
        )
        assert sensor_entity.unit_of_measurement == TEMP_CELSIUS

        state = hass.states.get(sensor_id)
        assert state.state == "25.1"


def test_onewiredirect_entity(hass):
    """Test that onewiredirect updates correctly."""
    with patch("pi1wire.OneWire") as owsensor:
        init_args = [
            MOCK_DEVICE_NAME,
            path.join(DEFAULT_SYSBUS_MOUNT_DIR, MOCK_DEVICE_ID, "w1_slave"),
            "temperature",
            owsensor.return_value,
        ]
    test_sensor = OneWireDirect(*init_args)

    assert test_sensor.name == f"{MOCK_DEVICE_NAME} Temperature"
    assert test_sensor.unit_of_measurement == TEMP_CELSIUS
    assert test_sensor.state is None

    owsensor.return_value.get_temperature.side_effect = [25.123]
    test_sensor.update()
    assert test_sensor.state == 25.1

    owsensor.return_value.get_temperature.side_effect = [InvalidCRCException]
    test_sensor.update()
    assert test_sensor.state is None

    owsensor.return_value.get_temperature.side_effect = [NotFoundSensorException]
    test_sensor.update()
    assert test_sensor.state is None

    owsensor.return_value.get_temperature.side_effect = [UnsupportResponseException]
    test_sensor.update()
    assert test_sensor.state is None

    owsensor.return_value.get_temperature.side_effect = [28.312]
    test_sensor.update()
    assert test_sensor.state == 28.3
