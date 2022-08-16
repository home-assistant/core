"""Tests for Srp Energy component Init."""
from homeassistant.components.srp_energy import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component


async def test_setup_with_no_config(hass):
    """Test that nothing is setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0

    # No configs stored
    assert DOMAIN not in hass.data


async def test_setup_entry(hass, init_integration):
    """Test setup entry."""
    assert init_integration.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN]


async def test_unload_entry(hass, init_integration):
    """Test being able to unload an entry."""
    assert init_integration.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN]

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert not hass.data[DOMAIN]
