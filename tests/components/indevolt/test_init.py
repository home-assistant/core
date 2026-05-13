"""Tests for the Indevolt integration initialization and services."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from . import setup_integration
from .conftest import DEVICE_MAPPING

from tests.common import MockConfigEntry


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_load_unload(
    hass: HomeAssistant, mock_indevolt: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and removing a config entry."""
    await setup_integration(hass, mock_config_entry)

    # Verify the config entry is successfully loaded
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Unload the integration
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the config entry is properly unloaded
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("generation", [1, 2], indirect=True)
async def test_device_info(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    generation: int,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that device info is correctly registered in the device registry."""
    await setup_integration(hass, mock_config_entry)

    device_info = DEVICE_MAPPING[generation]
    device_entry = device_registry.async_get_device(
        connections={(CONNECTION_NETWORK_MAC, device_info["mac"])}
    )

    assert device_entry is not None
    assert device_entry.manufacturer == "INDEVOLT"
    assert device_entry.model == device_info["device"]
    assert device_entry.serial_number == device_info["sn"]
    assert device_entry.sw_version == device_info["fw"]
    assert device_entry.hw_version == str(device_info["generation"])
    assert (CONNECTION_NETWORK_MAC, device_info["mac"]) in device_entry.connections


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_load_failure(
    hass: HomeAssistant, mock_indevolt: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup failure when coordinator update fails."""
    # Simulate timeout error during coordinator initialization
    mock_indevolt.get_config.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the config entry enters retry state due to failure
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
