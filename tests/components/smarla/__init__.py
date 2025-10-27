"""Tests for the Smarla integration."""

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> bool:
    """Set up the component."""
    config_entry.add_to_hass(hass)
    if success := await hass.config_entries.async_setup(config_entry.entry_id):
        await hass.async_block_till_done()
    return success


async def update_property_listeners(mock: AsyncMock, value: Any = None) -> None:
    """Update the property listeners for the mock object."""
    for call in mock.add_listener.call_args_list:
        await call[0][0](value)
