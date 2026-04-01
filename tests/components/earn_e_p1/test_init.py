"""Tests for the EARN-E P1 Meter integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import DOMAIN, MOCK_SERIAL, trigger_callback

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test successful setup of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_listener.start.assert_awaited_once()
    mock_listener.register.assert_called_once()


async def test_setup_entry_oserror_raises_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test that OSError during setup raises ConfigEntryNotReady."""
    mock_listener.start = AsyncMock(side_effect=OSError("Address in use"))

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test unloading a config entry stops the shared listener."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_listener.unregister.assert_called()
    mock_listener.stop.assert_awaited()


async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device info is correctly populated."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, MOCK_SERIAL)})
    assert device is not None
    assert device == snapshot
