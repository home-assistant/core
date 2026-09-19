"""Tests for Marantz RS-232 setup and teardown."""

import logging
from unittest.mock import patch

from marantz_rs232 import MarantzV2007Receiver
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Query both players and clean up subscriptions on unload."""
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_receiver.connect.assert_awaited_once()
    mock_receiver.query_state.assert_awaited_once()
    mock_receiver.query_multi_room_a.assert_awaited_once()
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        reload.assert_not_called()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_receiver.disconnect.assert_awaited_once()
    assert not mock_receiver._subscribers


@pytest.mark.parametrize("method", ["connect", "query_state", "query_multi_room_a"])
async def test_setup_failure(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
    mock_config_entry: MockConfigEntry,
    method: str,
) -> None:
    """Retry setup when either player's initial query fails."""
    getattr(mock_receiver, method).side_effect = ConnectionError("No response")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not mock_receiver.connected
    assert mock_config_entry.error_reason_translation_key == "communication_error"


@pytest.mark.usefixtures("init_integration")
async def test_remove_entry(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Do not reload a removed entry when disconnecting."""
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await hass.config_entries.async_remove(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        reload.assert_not_called()
    mock_receiver.disconnect.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_connection_logging(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Log one disconnect and one successful reconnection, at info level."""
    caplog.set_level(logging.INFO, logger="homeassistant.components.marantz_rs232")
    caplog.clear()
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await mock_receiver.disconnect()
        await mock_receiver.disconnect()
        reload.assert_called_once_with(mock_config_entry.entry_id)
    assert caplog.text.count("is unavailable; reconnecting") == 1

    with patch.object(
        mock_receiver, "connect", side_effect=OSError("Port unavailable")
    ):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert caplog.text.count("is unavailable; reconnecting") == 1
    assert "Connected to Marantz receiver" not in caplog.text

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert caplog.text.count("Connected to Marantz receiver") == 1
    assert all(
        record.levelno == logging.INFO
        for record in caplog.records
        if record.name == "homeassistant.components.marantz_rs232"
    )
