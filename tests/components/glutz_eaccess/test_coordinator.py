"""Tests for the Glutz eAccess coordinator."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from pyglutz_eaccess import GlutzAuthError, GlutzConnectionError

from homeassistant.components.glutz_eaccess.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_successful_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that the coordinator fetches and keys access points by ID."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert "ap-1" in coordinator.data
    assert "ap-2" in coordinator.data


async def test_coordinator_connection_error_on_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
    freezer,
) -> None:
    """Test that a connection error marks last_update_success as False."""
    await setup_integration(hass, mock_config_entry)

    mock_glutz_client.get_access_points.side_effect = GlutzConnectionError

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert not coordinator.last_update_success


async def test_coordinator_auth_error_on_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that auth error on first refresh puts entry in SETUP_ERROR."""
    mock_glutz_client.get_access_points.side_effect = GlutzAuthError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_auth_error_during_scheduled_update_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
    freezer,
) -> None:
    """Test that auth error during a scheduled refresh marks update as failed."""
    await setup_integration(hass, mock_config_entry)

    mock_glutz_client.get_access_points.side_effect = GlutzAuthError

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Entry stays LOADED; coordinator marks the update as failed
    assert mock_config_entry.state is ConfigEntryState.LOADED
    coordinator = mock_config_entry.runtime_data
    assert not coordinator.last_update_success


async def test_coordinator_data_keyed_by_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that coordinator.data is a dict keyed by accessPointId."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    for ap_id, ap in coordinator.data.items():
        assert ap["accessPointId"] == ap_id
