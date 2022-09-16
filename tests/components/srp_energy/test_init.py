"""Tests for Srp Energy component Init."""
from homeassistant.components.srp_energy import DOMAIN
from homeassistant.config_entries import ConfigEntryState


async def test_setup_entry(hass, init_integration):
    """Test setup entry."""
    assert init_integration.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN][init_integration.entry_id]


async def test_unload_entry(hass, init_integration):
    """Test being able to unload an entry."""
    assert init_integration.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN][init_integration.entry_id]

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.entry_id not in hass.data[DOMAIN]
