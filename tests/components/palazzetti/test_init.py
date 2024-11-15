"""Tests for the Palazzetti integration."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_palazzetti_client: AsyncMock,
) -> None:
    """Test the Palazzetti configuration entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_palazzetti_client: AsyncMock,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device information."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "11:22:33:44:55:66")}
    )
    assert device is not None
    assert device == snapshot
