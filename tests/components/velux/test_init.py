"""Tests for the Velux component initialisation."""
from unittest.mock import patch

from homeassistant.components.velux import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TestPyVLX


@patch("homeassistant.components.velux.PyVLX", new=TestPyVLX)
async def test_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Test loading and unloading setup entry."""
    assert not hass.data.get(DOMAIN)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state == ConfigEntryState.LOADED
    pyvlx: TestPyVLX = hass.data[DOMAIN][config_entry.entry_id]
    assert not pyvlx.reboot_initiated
    assert not pyvlx.disconnected
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert pyvlx.reboot_initiated
    assert pyvlx.disconnected
    assert config_entry.state == ConfigEntryState.NOT_LOADED


@patch("homeassistant.components.velux.PyVLX", new=TestPyVLX)
async def test_reboot_service(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Test reboot service."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    pyvlx: TestPyVLX = hass.data[DOMAIN][config_entry.entry_id]
    assert not pyvlx.reboot_initiated
    await hass.services.async_call(DOMAIN, "reboot_gateway")
    await hass.async_block_till_done()
    assert pyvlx.reboot_initiated
