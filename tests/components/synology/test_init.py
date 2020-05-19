"""Test setting up synology platform."""
from homeassistant.components import synology
from homeassistant.components.synology.const import DOMAIN
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from . import (
    CAMERA1_ENTITY_ID,
    CAMERA1_NAME,
    CAMERA2_ENTITY_ID,
    CAMERA2_NAME,
    CONF_ENTRY,
    _patch_camera_device,
    _patch_config_flow_device,
)

from tests.common import MockConfigEntry


async def test_setup_empty(hass: HomeAssistantType):
    """Test setup without any configuration."""
    assert await async_setup_component(hass, DOMAIN, {}) is True
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_setup(hass: HomeAssistantType):
    """Test setup platform."""
    with _patch_config_flow_device(), _patch_camera_device() as device:
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: [CONF_ENTRY]}) is True
        await hass.async_block_till_done()
        device.assert_called_once()
    assert hass.states.get(CAMERA1_ENTITY_ID).name == CAMERA1_NAME
    assert hass.states.get(CAMERA2_ENTITY_ID).name == CAMERA2_NAME


async def test_unload(hass: HomeAssistantType):
    """Test unload entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONF_ENTRY)
    entry.add_to_hass(hass)

    with _patch_camera_device(), _patch_camera_device():
        assert await async_setup_component(hass, DOMAIN, {}) is True
        await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    assert await synology.async_unload_entry(hass, entry)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
