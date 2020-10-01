"""Tests for 1-Wire device family 28 (DS18B20)."""
from os import path
from unittest.mock import Mock, mock_open, patch

from pyownet import protocol

from homeassistant import util
from homeassistant.components.onewire.const import (
    DEFAULT_OWSERVER_PORT,
    DEFAULT_SYSBUS_MOUNT_DIR,
)
from homeassistant.components.onewire.sensor import (
    OneWireDirect,
    OneWireOWFS,
    OneWireProxy,
)
import homeassistant.components.sensor as sensor
from homeassistant.const import TEMP_CELSIUS
from homeassistant.setup import async_setup_component

from tests.common import mock_registry

OWFS_MOUNT_DIR = "/mnt/OneWireTest"

DEVICE_ID = "28.111111111111"
DEVICE_NAME = "My DS18B20"


async def test_setup_sysbus(hass):
    """Test setup with SysBus configuration."""
    entity_registry = mock_registry(hass)
    device_id = DEVICE_ID.replace(".", "-")
    config = {
        "sensor": {
            "platform": "onewire",
            "names": {
                device_id: DEVICE_NAME,
            },
        }
    }
    with patch(
        "homeassistant.components.onewire.sensor.glob",
        return_value=[path.join(DEFAULT_SYSBUS_MOUNT_DIR, device_id)],
    ), patch(
        "homeassistant.components.onewire.sensor.open",
        mock_open(read_data=": crc=09 YES\nt=25123"),
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, config)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == 1
    sensor_id = "sensor." + util.slugify(DEVICE_NAME) + "_temperature"
    sensor_entity = entity_registry.entities.get(sensor_id)
    assert sensor_entity is not None
    assert sensor_entity.unique_id == path.join(
        DEFAULT_SYSBUS_MOUNT_DIR, device_id, "w1_slave"
    )
    assert sensor_entity.unit_of_measurement == TEMP_CELSIUS

    state = hass.states.get(sensor_id)
    assert state.state == "25.1"


async def test_setup_owfs(hass):
    """Test setup with OWFS configuration."""
    entity_registry = mock_registry(hass)
    config = {
        "sensor": {
            "platform": "onewire",
            "mount_dir": OWFS_MOUNT_DIR,
            "names": {
                DEVICE_ID: DEVICE_NAME,
            },
        }
    }
    mo_main = mo_family = mock_open(read_data=DEVICE_ID[0:2])
    mo_temperature = mock_open(read_data="    25.123")
    mo_main.side_effect = [
        mo_family.return_value,
        mo_temperature.return_value,
    ]
    with patch(
        "homeassistant.components.onewire.sensor.glob",
        return_value=[path.join(OWFS_MOUNT_DIR, DEVICE_ID, "family")],
    ), patch(
        "homeassistant.components.onewire.sensor.open",
        mo_main,
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, config)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == 1
    sensor_id = "sensor." + util.slugify(DEVICE_NAME) + "_temperature"
    sensor_entity = entity_registry.entities.get(sensor_id)
    assert sensor_entity is not None
    assert sensor_entity.unique_id == path.join(
        OWFS_MOUNT_DIR, DEVICE_ID, "temperature"
    )
    assert sensor_entity.unit_of_measurement == TEMP_CELSIUS

    state = hass.states.get(sensor_id)
    assert state.state == "25.1"


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
    assert sensor_entity.unique_id == "/" + path.join(DEVICE_ID, "temperature")
    assert sensor_entity.unit_of_measurement == TEMP_CELSIUS

    state = hass.states.get(sensor_id)
    assert state.state == "25.1"


def test_onewireowfs_update(hass):
    """Test that onewireowfs updates correctly."""
    init_args = [
        DEVICE_NAME,
        path.join(OWFS_MOUNT_DIR, DEVICE_ID, "temperature"),
        "temperature",
    ]

    test_sensor = OneWireOWFS(*init_args)

    mo_main = mock_open(read_data="    25.123")
    with patch(
        "homeassistant.components.onewire.sensor.open",
        mo_main,
    ):
        test_sensor.update()
        assert test_sensor.state == 25.1

    # ValueError
    mo_main = mock_open(read_data="    25A123")
    with patch(
        "homeassistant.components.onewire.sensor.open",
        mo_main,
    ):
        test_sensor.update()
        assert test_sensor.state is None

    mo_main = mock_open(read_data="")
    mo_main.side_effect = FileNotFoundError
    with patch(
        "homeassistant.components.onewire.sensor.open",
        mo_main,
    ):
        test_sensor.update()
        assert test_sensor.state is None


def test_onewireproxy_update(hass):
    """Test that onewireproxy updates correctly."""
    owproxy = Mock()

    init_args = [
        DEVICE_NAME,
        "/" + path.join(DEVICE_ID, "temperature"),
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
        "/" + path.join(DEVICE_ID, "temperature"),
        "temperature",
        owproxy,
    ]

    test_sensor = OneWireProxy(*init_args)
    test_sensor.update()
    assert test_sensor.state is None
