"""Tests for Marantz RS-232 setup and teardown."""

import asyncio
import logging
from unittest.mock import patch

from marantz_rs232 import MarantzV2007Receiver
import pytest

from homeassistant.components.marantz_rs232.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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


@pytest.mark.parametrize("method", ["query_state", "query_multi_room_a"])
async def test_unexpected_query_failure(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
    mock_config_entry: MockConfigEntry,
    method: str,
) -> None:
    """Close the connection when an initial query raises an unexpected error."""
    getattr(mock_receiver, method).side_effect = RuntimeError("Unexpected query error")
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_receiver.disconnect.assert_awaited_once()
    assert not mock_receiver.connected


async def test_platform_forwarding_failure(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Close the connection and remove subscriptions when platform forwarding fails."""
    mock_config_entry.add_to_hass(hass)
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=RuntimeError("Unexpected platform error"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_receiver.disconnect.assert_awaited_once()
    assert not mock_receiver.connected
    assert not mock_receiver._subscribers


async def test_cancelled_setup(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
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
    mock_receiver: MarantzV2007Receiver,
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
    """Log a disconnect once without duplicating library connection messages."""
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
    assert "Connected to Marantz receiver" not in caplog.text
    assert all(
        record.levelno == logging.INFO
        for record in caplog.records
        if record.name == "homeassistant.components.marantz_rs232"
    )


@pytest.mark.parametrize("method", ["connect", "query_state"])
async def test_invalid_serial_port(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
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
    mock_receiver: MarantzV2007Receiver,
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
