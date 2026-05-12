"""Tests for the Glutz eAccess integration."""
from __future__ import annotations

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the Glutz eAccess integration for testing."""
    # Lock platform registers services whose translations are validated by the
    # autouse check_translations fixture; loading lock domain first ensures
    # its translations are in cache before our entry's platform setup runs.
    await async_setup_component(hass, LOCK_DOMAIN, {})
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
