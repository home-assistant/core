"""Tests for Marantz RS-232 setup and teardown."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from marantz_rs232 import V2007ReceiverState
import pytest
from serialx import SerialException

from homeassistant.components.marantz_rs232.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("init_integration")
async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Query both players and clean up subscriptions on unload."""
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_receiver.connect.assert_awaited_once()
    mock_receiver.query_state.assert_awaited_once()
    mock_receiver.query_multi_room_a.assert_awaited_once()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_receiver.connect.assert_awaited_once()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_receiver.disconnect.assert_awaited_once()


@pytest.mark.parametrize("method", ["connect", "query_state", "query_multi_room_a"])
async def test_setup_failure(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
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


async def test_cancelled_setup(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Close the connection when setup is cancelled during the initial query."""
    query_started = asyncio.Event()

    async def query_state() -> None:
        query_started.set()
        await asyncio.Event().wait()

    mock_receiver.query_state.side_effect = query_state
    mock_config_entry.add_to_hass(hass)
    task = hass.async_create_task(
        hass.config_entries.async_setup(mock_config_entry.entry_id)
    )
    await query_started.wait()
    assert mock_receiver.connected
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await hass.async_block_till_done()
    mock_receiver.disconnect.assert_awaited_once()
    assert not mock_receiver.connected


@pytest.mark.usefixtures("init_integration")
async def test_failed_unload(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Keep the connection open when the platform cannot unload."""
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(mock_config_entry.entry_id)
    mock_receiver.disconnect.assert_not_awaited()
    assert mock_receiver.connected


@pytest.mark.usefixtures("init_integration")
async def test_remove_entry(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Do not reload a removed entry when disconnecting."""
    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_receiver.connect.assert_awaited_once()
    mock_receiver.disconnect.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_connection_logging(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    mock_config_entry: MockConfigEntry,
    receiver_update: Callable[[V2007ReceiverState | None], None],
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Log one outage while Home Assistant retries the connection."""
    await hass.async_start()
    caplog.clear()
    connect = mock_receiver.connect.side_effect
    mock_receiver.connect.side_effect = OSError("Port unavailable")
    receiver_update(None)
    receiver_update(None)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_receiver.connect.await_count == 2
    assert caplog.text.count("is unavailable; reconnecting") == 1

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_receiver.connect.await_count == 3
    assert caplog.text.count("is unavailable; reconnecting") == 1

    mock_receiver.connect.side_effect = connect
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_receiver.connect.await_count == 4
    assert mock_receiver.query_state.await_count == 2
    assert "Connected to Marantz receiver" not in caplog.text
    assert (
        f"homeassistant.components.{DOMAIN}",
        logging.INFO,
        "Marantz receiver is unavailable; reconnecting",
    ) in caplog.record_tuples


@pytest.mark.parametrize("method", ["connect", "query_state"])
async def test_invalid_serial_port(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    mock_config_entry: MockConfigEntry,
    method: str,
) -> None:
    """Report invalid serial configuration without endlessly retrying it."""
    getattr(mock_receiver, method).side_effect = ValueError("Invalid serial endpoint")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "invalid_serial_port"
    assert not mock_receiver.connected


async def test_generic_receiver(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Use the generic protocol without claiming to know the receiver model."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.marantz_rs232.MarantzV2007Receiver",
        return_value=mock_receiver,
    ) as constructor:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    constructor.assert_called_once_with(mock_config_entry.data[CONF_DEVICE])
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Marantz"
    assert device.model is None
    assert device.model_id is None


async def test_setup_serial_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Retry setup when the serial transport cannot be opened."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "serialx.open_serial_connection",
        side_effect=SerialException("Serial proxy is unavailable"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
