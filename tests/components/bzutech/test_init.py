"""Test loading and unloading in the bzutech integration."""

from homeassistant.components.bzutech.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import USER_INPUT, init_integration


async def test_unload_entry(hass: HomeAssistant, bzutech) -> None:
    """Test entry unload."""
    entry = await init_integration(hass, data=USER_INPUT)

    assert entry
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry_id=entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
