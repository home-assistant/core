"""Tests for the Marantz RS-232 integration setup and teardown."""

from marantz_rs232 import MarantzV2015Receiver

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_v2015_receiver: MarantzV2015Receiver,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a config entry sets up and unloads cleanly."""
    await setup_integration(
        hass, mock_config_entry, mock_v2015_receiver, "MarantzV2015Receiver"
    )

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_v2015_receiver.connect.assert_awaited_once()
    mock_v2015_receiver.query_state.assert_awaited_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_v2015_receiver.disconnect.assert_awaited_once()


async def test_setup_connect_failure_raises_not_ready(
    hass: HomeAssistant,
    mock_v2015_receiver: MarantzV2015Receiver,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a connection failure puts the entry in retry state."""
    mock_v2015_receiver.connect.side_effect = ConnectionError("No response")

    await setup_integration(
        hass, mock_config_entry, mock_v2015_receiver, "MarantzV2015Receiver"
    )

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_v2015_receiver.disconnect.assert_awaited_once()


async def test_remove_entry_while_loaded(
    hass: HomeAssistant,
    mock_v2015_receiver: MarantzV2015Receiver,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing a loaded entry does not schedule a reload.

    When removing a loaded entry, disconnect() fires the subscriber callback
    with state=None. The callback must not schedule a reload because the entry
    is already being removed (state is no longer LOADED).
    """
    await setup_integration(
        hass, mock_config_entry, mock_v2015_receiver, "MarantzV2015Receiver"
    )
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_v2015_receiver.disconnect.assert_awaited_once()
