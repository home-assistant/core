"""Tests for 1-Wire device family 00 (Invalid device)."""
from unittest.mock import patch

from homeassistant.components.onewire.const import DEFAULT_OWSERVER_PORT
import homeassistant.components.sensor as sensor
from homeassistant.setup import async_setup_component

from tests.common import mock_registry

OWFS_MOUNT_DIR = "/mnt/OneWireTest"

DEVICE_ID = "00.111111111111"
DEVICE_NAME = "My invalid device"


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
