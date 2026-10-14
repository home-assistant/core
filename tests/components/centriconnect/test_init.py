"""Tests for the CentriConnect/MyPropane configuration initialization."""

from unittest.mock import AsyncMock

from aiocentriconnect.exceptions import CentriConnectConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.centriconnect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_centriconnect_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry == snapshot


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_centriconnect_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry not ready."""
    mock_centriconnect_client.async_get_tank_data.side_effect = (
        CentriConnectConnectionError
    )
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_centriconnect_client.async_get_tank_data.side_effect = None
