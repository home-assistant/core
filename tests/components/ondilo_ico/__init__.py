"""Tests for the Ondilo ICO integration."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_ondilo_client: MagicMock
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
