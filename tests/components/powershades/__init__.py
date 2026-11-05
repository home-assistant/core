"""Tests for the PowerShades integration."""

from unittest.mock import MagicMock

from pyowershades import StatusReply
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the PowerShades integration for a config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def push_status(
    hass: HomeAssistant, connection: MagicMock, position: int | None
) -> None:
    """Push a status update through the callback given to the library."""
    status_callback = connection.set_status_callback.call_args.args[0]
    status_callback(StatusReply(position=position, battery_mv=3700))
    await hass.async_block_till_done()
