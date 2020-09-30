"""Tests for 1-Wire device family 00 (Invalid device)."""
from os import path
from unittest.mock import mock_open, patch

from homeassistant.components.onewire.const import (
    DEFAULT_OWSERVER_PORT,
    DEFAULT_SYSBUS_MOUNT_DIR,
)
import homeassistant.components.sensor as sensor
from homeassistant.setup import async_setup_component

from tests.common import mock_registry

OWFS_MOUNT_DIR = "/mnt/OneWireTest"

DEVICE_ID = "00.111111111111"
DEVICE_NAME = "My invalid device"


async def test_setup_sysbus(hass):
    """Test a device which is not recognised."""
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
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, config)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == 0


async def test_setup_owfs(hass):
    """Test a device which is not recognised."""
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
        owproxy.return_value.read.return_value = DEVICE_ID[0:2].encode()
        assert await async_setup_component(hass, sensor.DOMAIN, config)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == 0
