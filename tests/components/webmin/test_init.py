"""Tests for the Webmin integration."""

from homeassistant.components.webmin.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import async_init_integration


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""

    entry = await async_init_integration(hass)

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
