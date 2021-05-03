"""Test the Coinbase integration."""
from homeassistant.components.coinbase.const import DOMAIN
from homeassistant.config_entries import ENTRY_STATE_LOADED, ENTRY_STATE_NOT_LOADED

from .common import init_mock_coinbase


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    entry = await init_mock_coinbase(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)
