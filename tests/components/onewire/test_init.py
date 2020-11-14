"""Tests for 1-Wire config flow."""
from homeassistant.components.onewire.const import DOMAIN
from homeassistant.config_entries import ENTRY_STATE_LOADED, ENTRY_STATE_NOT_LOADED

from . import setup_onewire_owserver_integration, setup_onewire_sysbus_integration


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    config_entry_owserver = await setup_onewire_owserver_integration(hass)
    config_entry_sysbus = await setup_onewire_sysbus_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert config_entry_owserver.state == ENTRY_STATE_LOADED
    assert config_entry_sysbus.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(config_entry_owserver.entry_id)
    assert await hass.config_entries.async_unload(config_entry_sysbus.entry_id)
    await hass.async_block_till_done()

    assert config_entry_owserver.state == ENTRY_STATE_NOT_LOADED
    assert config_entry_sysbus.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)
