"""Tests for the Bambu Lab integration."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Bambu Lab integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def push_update(client: MagicMock) -> None:
    """Tell the listeners of the client that the printer changed."""
    for call in client.add_listener.call_args_list:
        call.args[0]()
