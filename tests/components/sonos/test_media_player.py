"""Tests for the Sonos Media Player platform."""
from homeassistant.components.sonos import media_player, DOMAIN
from homeassistant.setup import async_setup_component


async def setup_platform(hass, config_entry, config):
    """Set up the media player platform for testing."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_async_setup_entry_hosts(hass, config_entry, config, soco):
    """Test static setup."""
    await setup_platform(hass, config_entry, config)
    assert hass.data[media_player.DATA_SONOS].entities[0].soco == soco


async def test_async_setup_entry_discover(hass, config_entry, discover):
    """Test discovery setup."""
    await setup_platform(hass, config_entry, {})
    assert hass.data[media_player.DATA_SONOS].uids == {'RINCON_test'}
