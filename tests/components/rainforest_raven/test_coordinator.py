"""Tests for the Rainforest RAVEn data coordinator."""

import asyncio
import functools
from unittest.mock import AsyncMock, patch

from aioraven.device import RAVEnConnectionError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.rainforest_raven.coordinator import RAVEnDataCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import create_mock_entry


async def test_coordinator_cache_device(
    hass: HomeAssistant, mock_device: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test that the device isn't re-opened for subsequent refreshes."""
    entry = create_mock_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    assert mock_device.get_network_info.call_count == 1
    assert mock_device.open.call_count == 1

    coordinator: RAVEnDataCoordinator = entry.runtime_data
    await coordinator.async_refresh()

    assert mock_device.get_network_info.call_count == 2
    assert mock_device.open.call_count == 1


async def test_coordinator_device_error_setup(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test handling of a device error during initialization."""
    entry = create_mock_entry()
    entry.add_to_hass(hass)

    mock_device.get_network_info.side_effect = RAVEnConnectionError
    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_device_error_update(
    hass: HomeAssistant, mock_device: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test handling of a device error during an update."""
    entry = create_mock_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    coordinator: RAVEnDataCoordinator = entry.runtime_data
    assert coordinator.last_update_success is True

    mock_device.get_network_info.side_effect = RAVEnConnectionError
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False


async def test_coordinator_device_timeout_update(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test handling of a device timeout during an update."""
    entry = create_mock_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    coordinator: RAVEnDataCoordinator = entry.runtime_data
    assert coordinator.last_update_success is True

    assert len(coordinator._listeners) > 0

    mock_device.get_network_info.side_effect = functools.partial(asyncio.sleep, 10)
    with patch(
        "homeassistant.components.rainforest_raven.coordinator._DEVICE_TIMEOUT", 0.1
    ):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_coordinator_comm_error(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test handling of an error parsing or reading raw device data."""
    entry = create_mock_entry()
    entry.add_to_hass(hass)

    mock_device.synchronize.side_effect = RAVEnConnectionError

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
