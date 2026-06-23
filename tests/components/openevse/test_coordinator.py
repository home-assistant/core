"""Tests for the OpenEVSE coordinator."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_websocket_callback_updates_listeners(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test the websocket callback pushes updates to coordinator listeners."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data
    listener = MagicMock()
    coordinator.async_add_listener(listener)

    await mock_charger.callback()
    await hass.async_block_till_done()

    listener.assert_called_once()
