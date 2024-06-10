"""Tests for the Rainforest RAVEn data coordinator."""

import asyncio
import functools
from unittest.mock import AsyncMock

from aioraven.device import RAVEnConnectionError
import pytest

from homeassistant.components.rainforest_raven.coordinator import RAVEnDataCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from . import create_mock_entry


@pytest.mark.usefixtures("mock_device")
async def test_coordinator_device_info(hass: HomeAssistant) -> None:
    """Test reporting device information from the coordinator."""
    entry = create_mock_entry()
    coordinator = RAVEnDataCoordinator(hass, entry)

    assert coordinator.device_fw_version is None
    assert coordinator.device_hw_version is None
    assert coordinator.device_info is None
    assert coordinator.device_mac_address is None
    assert coordinator.device_manufacturer is None
    assert coordinator.device_model is None
    assert coordinator.device_name == "RAVEn Device"

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.device_fw_version == "2.0.0 (7400)"
    assert coordinator.device_hw_version == "2.7.3"
    assert coordinator.device_info
    assert coordinator.device_mac_address
    assert coordinator.device_manufacturer == "Rainforest Automation, Inc."
    assert coordinator.device_model == "Z105-2-EMU2-LEDD_JM"
    assert coordinator.device_name == "RAVEn Device"


async def test_coordinator_cache_device(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test that the device isn't re-opened for subsequent refreshes."""
    entry = create_mock_entry()
    coordinator = RAVEnDataCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    assert mock_device.get_network_info.call_count == 1
    assert mock_device.open.call_count == 1

    await coordinator.async_refresh()
    assert mock_device.get_network_info.call_count == 2
    assert mock_device.open.call_count == 1


async def test_coordinator_device_error_setup(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test handling of a device error during initialization."""
    entry = create_mock_entry()
    coordinator = RAVEnDataCoordinator(hass, entry)

    mock_device.get_network_info.side_effect = RAVEnConnectionError
    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()


async def test_coordinator_device_error_update(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test handling of a device error during an update."""
    entry = create_mock_entry()
    coordinator = RAVEnDataCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    assert coordinator.last_update_success is True

    mock_device.get_network_info.side_effect = RAVEnConnectionError
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False


async def test_coordinator_device_timeout_update(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test handling of a device timeout during an update."""
    entry = create_mock_entry()
    coordinator = RAVEnDataCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    assert coordinator.last_update_success is True

    mock_device.get_network_info.side_effect = functools.partial(asyncio.sleep, 10)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False


async def test_coordinator_comm_error(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test handling of an error parsing or reading raw device data."""
    entry = create_mock_entry()
    coordinator = RAVEnDataCoordinator(hass, entry)

    mock_device.synchronize.side_effect = RAVEnConnectionError
    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()
