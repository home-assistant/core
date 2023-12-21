"""Tests for the Velux component initialisation."""
from unittest.mock import patch

from homeassistant.components.velux.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .conftest import TestPyVLX


async def test_async_setup(hass: HomeAssistant, config_type: ConfigType) -> None:
    """Test velux setup via configuration.yaml."""
    assert not hass.data.get(DOMAIN)
    assert await async_setup_component(hass=hass, domain=DOMAIN, config=config_type)
    await hass.async_block_till_done()


@patch("homeassistant.components.velux.PyVLX", new=TestPyVLX)
async def test_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Test velux setup via configuration.yaml."""
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
