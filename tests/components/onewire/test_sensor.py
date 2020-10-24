"""Tests for 1-Wire sensor platform."""
from homeassistant.components.onewire.const import DEFAULT_SYSBUS_MOUNT_DIR
import homeassistant.components.sensor as sensor
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component


async def test_setup_minimum(hass):
    """Test old platform setup with minimum configuration."""
    config = {"sensor": {"platform": "onewire"}}
    with assert_setup_component(1, "sensor"):
        assert await async_setup_component(hass, sensor.DOMAIN, config)
    await hass.async_block_till_done()


async def test_setup_sysbus(hass):
    """Test old platform setup with SysBus configuration."""
    config = {
        "sensor": {
            "platform": "onewire",
            "mount_dir": DEFAULT_SYSBUS_MOUNT_DIR,
        }
    }
    with assert_setup_component(1, "sensor"):
        assert await async_setup_component(hass, sensor.DOMAIN, config)
    await hass.async_block_till_done()


async def test_setup_owserver(hass):
    """Test old platform setup with OWServer configuration."""
    config = {"sensor": {"platform": "onewire", "host": "localhost"}}
    with assert_setup_component(1, "sensor"):
        assert await async_setup_component(hass, sensor.DOMAIN, config)
    await hass.async_block_till_done()


async def test_setup_owserver_with_port(hass):
    """Test old platform setup with OWServer configuration."""
    config = {"sensor": {"platform": "onewire", "host": "localhost", "port": "1234"}}
    with assert_setup_component(1, "sensor"):
        assert await async_setup_component(hass, sensor.DOMAIN, config)
    await hass.async_block_till_done()
