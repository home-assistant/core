"""Tests for 1-Wire device family 28 (DS18B20)."""
from unittest.mock import Mock, patch

from pyownet import protocol

from homeassistant import util
from homeassistant.components.onewire.const import DEFAULT_OWSERVER_PORT
from homeassistant.components.onewire.sensor import OneWireProxy
import homeassistant.components.sensor as sensor
from homeassistant.const import TEMP_CELSIUS
from homeassistant.setup import async_setup_component

from tests.common import mock_registry

DEVICE_ID = "28.111111111111"
DEVICE_NAME = "My DS18B20"


async def test_owserver_setup(hass):
    """Test setup with OWServer configuration."""
    entity_registry = mock_registry(hass)
    config = {
        "sensor": {
            "platform": "onewire",
            "host": "localhost",
            "port": DEFAULT_OWSERVER_PORT,
            "names": {
                DEVICE_ID: DEVICE_NAME,
            },
        }
    }
    with patch(
        "homeassistant.components.onewire.sensor.protocol.proxy",
    ) as owproxy:
        owproxy.return_value.dir.return_value = [f"/{DEVICE_ID}/"]
        owproxy.return_value.read.side_effect = [
            DEVICE_ID[0:2].encode(),  # read the family
            b"    25.123",  # read the value
        ]

        assert await async_setup_component(hass, sensor.DOMAIN, config)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == 1
    sensor_id = "sensor." + util.slugify(DEVICE_NAME) + "_temperature"
    sensor_entity = entity_registry.entities.get(sensor_id)
    assert sensor_entity is not None
    assert sensor_entity.unique_id == f"/{DEVICE_ID}/temperature"
    assert sensor_entity.unit_of_measurement == TEMP_CELSIUS

    state = hass.states.get(sensor_id)
    assert state.state == "25.1"


def test_onewireproxy_update(hass):
    """Test that onewireproxy updates correctly."""
    owproxy = Mock()

    init_args = [
        DEVICE_NAME,
        f"/{DEVICE_ID}/temperature",
        "temperature",
        owproxy,
    ]
    test_sensor = OneWireProxy(*init_args)

    owproxy.read.return_value = b"    25.72"
    test_sensor.update()
    assert test_sensor.state == 25.7

    owproxy.read.side_effect = protocol.Error
    test_sensor.update()
    assert test_sensor.state is None


def test_onewireproxy_missingproxy(hass):
    """Test updates when owproxy is None."""
    owproxy = None

    init_args = [
        DEVICE_NAME,
        f"/{DEVICE_ID}/temperature",
        "temperature",
        owproxy,
    ]

    test_sensor = OneWireProxy(*init_args)
    test_sensor.update()
    assert test_sensor.state is None
