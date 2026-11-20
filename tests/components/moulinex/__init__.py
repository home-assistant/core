"""Tests for the Moulinex integration."""

from unittest.mock import MagicMock

from aiomoulinex import ApplianceState, ApplianceUpdated, Event
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the Moulinex integration for testing."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def push_event(client: MagicMock, event: Event) -> None:
    """Send an event to the listener the integration registered on the client."""
    client.add_listener.call_args.args[0](event)


def push_state(client: MagicMock, appliance_id: str, state: ApplianceState) -> None:
    """Make an appliance push a new state."""
    client.states = {**client.states, appliance_id: state}
    push_event(client, ApplianceUpdated(client.appliances[appliance_id], state))
