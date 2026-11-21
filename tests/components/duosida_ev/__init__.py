"""Tests for the Duosida EV Charger integration."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the integration."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def push_update(client: MagicMock) -> None:
    """Call the listener the integration registered on the charger session."""
    client.add_listener.call_args.args[0]()
