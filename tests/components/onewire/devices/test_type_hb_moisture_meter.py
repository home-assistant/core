"""Tests for 1-Wire device type HB_MOISTURE_METER (family EF)."""
from os import path
from unittest.mock import mock_open, patch

from homeassistant import util
from homeassistant.components.onewire.const import DEFAULT_OWSERVER_PORT
import homeassistant.components.sensor as sensor
from homeassistant.setup import async_setup_component

from tests.common import mock_registry

OWFS_MOUNT_DIR = "/mnt/OneWireTest"

DEVICE_ID = "EF.111111111111"
DEVICE_NAME = "My HB_MOISTURE_METER"
DEVICE_TYPE = "HB_MOISTURE_METER"


async def test_setup_owfs(hass):
    """Test a device which is not recognised on OWFS."""
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
    mo_main.side_effect = [
        mo_family.return_value,
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

    assert len(entity_registry.entities) == 0


async def test_setup_owserver(hass):
    """Test a hobbyboard (HB_MOISTURE_METER) on OWServer."""
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
            DEVICE_ID[0:2].encode(),
            DEVICE_TYPE.encode(),  # read type
            b"         1",  # read is_leaf_0
            b"         1",  # read is_leaf_1
            b"         0",  # read is_leaf_2
            b"         0",  # read is_leaf_3
            b"    41.745",  # read moisture_0
            b"    42.541",  # read moisture_1
            b"    43.123",  # read moisture_2
            b"    44.123",  # read moisture_3
        ]
        assert await async_setup_component(hass, sensor.DOMAIN, config)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == 4

    # is_leaf = 1
    sensor_id = "sensor." + util.slugify(DEVICE_NAME) + "_wetness_0"
    state = hass.states.get(sensor_id)
    assert state.state == "41.7"

    # is_leaf = 1
    sensor_id = "sensor." + util.slugify(DEVICE_NAME) + "_wetness_1"
    state = hass.states.get(sensor_id)
    assert state.state == "42.5"

    # is_leaf = 0
    sensor_id = "sensor." + util.slugify(DEVICE_NAME) + "_moisture_2"
    state = hass.states.get(sensor_id)
    assert state.state == "43.1"

    # is_leaf = 0
    sensor_id = "sensor." + util.slugify(DEVICE_NAME) + "_moisture_3"
    state = hass.states.get(sensor_id)
    assert state.state == "44.1"
