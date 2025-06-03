"""Tests for the Rainforest RAVEn component initialisation."""

from unittest.mock import AsyncMock

from aioraven.data import DeviceInfo as RAVenDeviceInfo
from aioraven.device import RAVEnConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rainforest_raven.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import create_mock_entry
from .const import DEVICE_INFO

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Test load and unload."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("device_info", "device_count"),
    [(DEVICE_INFO, 1), (None, 0)],
)
async def test_device_registry(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    device_info: RAVenDeviceInfo | None,
    device_count: int,
) -> None:
    """Test device registry, including if get_device_info returns None."""
    mock_device.get_device_info.return_value = device_info
    entry = create_mock_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED

    assert len(hass.states.async_all()) == 5

    entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert len(entries) == device_count
    assert entries == snapshot


async def test_synchronize_error(hass: HomeAssistant, mock_device: AsyncMock) -> None:
    """Test handling of an error parsing or reading raw device data."""
    entry = create_mock_entry()
    entry.add_to_hass(hass)

    mock_device.synchronize.side_effect = RAVEnConnectionError

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_network_info_error(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test handling of a device error during initialization."""
    entry = create_mock_entry()
    entry.add_to_hass(hass)

    mock_device.get_network_info.side_effect = RAVEnConnectionError
    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
