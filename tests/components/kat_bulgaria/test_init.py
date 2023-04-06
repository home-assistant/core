"""Test init."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.kat_bulgaria import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_basic_setup(hass: HomeAssistant) -> None:
    """Test component setup creates entry from config."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == config_entries.ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
