"""Tests for FritzBox VPN coordinator and session helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.fritzbox_vpn.const import (
    CONF_UPDATE_INTERVAL,
    STATUS_CONNECTED,
    STATUS_DISABLED,
    STATUS_ENABLED,
)
from custom_components.fritzbox_vpn.coordinator import (
    FritzBoxVPNCoordinator,
    normalize_update_interval,
)
from fritzboxvpn.parsing import normalize_box_connections
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_HOST, MOCK_PASSWORD, MOCK_USERNAME, MOCK_VPN_CONNECTIONS


def test_normalize_update_interval_clamps_and_defaults() -> None:
    """Update interval is clamped to allowed range."""
    assert normalize_update_interval(30) == 30
    assert normalize_update_interval(1) == 30
    assert normalize_update_interval(None) == 30
    assert normalize_update_interval("120") == 120


def test_normalize_box_connections_list_and_dict() -> None:
    """boxConnections list/dict payloads normalize to uid-keyed dict."""
    listed = normalize_box_connections(
        [{"uid": "a", "active": 1, "name": "A"}]
    )
    assert listed["a"]["active"] is True

    keyed = normalize_box_connections(
        {"b": {"uid": "", "active": "true", "name": "B"}}
    )
    assert "b" in keyed
    assert keyed["b"]["active"] is True


@pytest.mark.asyncio
async def test_coordinator_update_success(hass: HomeAssistant) -> None:
    """Coordinator stores VPN data from session."""
    entry = MockConfigEntry(
        domain="fritzbox_vpn",
        data={
            "host": MOCK_HOST,
            "username": MOCK_USERNAME,
            "password": MOCK_PASSWORD,
        },
    )
    coordinator = FritzBoxVPNCoordinator(
        hass,
        entry.data,
        {CONF_UPDATE_INTERVAL: 60},
        entry.entry_id,
    )
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        return_value=MOCK_VPN_CONNECTIONS
    )

    data = await coordinator._async_update_data()
    coordinator.data = data
    assert data == MOCK_VPN_CONNECTIONS
    assert coordinator.get_vpn_status("conn-abc") == STATUS_ENABLED
    assert coordinator.get_vpn_status("conn-def") == STATUS_DISABLED


@pytest.mark.asyncio
async def test_coordinator_status_connected(hass: HomeAssistant) -> None:
    """Connected VPN reports connected status."""
    entry = MockConfigEntry(
        domain="fritzbox_vpn",
        data={"host": MOCK_HOST, "username": "u", "password": "p"},
    )
    coordinator = FritzBoxVPNCoordinator(hass, entry.data, None, entry.entry_id)
    coordinator.data = {
        "x": {"active": True, "connected": True},
    }
    assert coordinator.get_vpn_status("x") == STATUS_CONNECTED


@pytest.mark.asyncio
async def test_schedule_reauth_only_once(hass: HomeAssistant) -> None:
    """Reauth is scheduled at most once until a successful update."""
    entry = MockConfigEntry(
        domain="fritzbox_vpn",
        data={"host": MOCK_HOST, "username": "u", "password": "p"},
    )
    entry.add_to_hass(hass)
    coordinator = FritzBoxVPNCoordinator(hass, entry.data, None, entry.entry_id)

    mock_entry = MagicMock()
    mock_entry.async_start_reauth = AsyncMock()
    mock_entry.state = ConfigEntryState.LOADED

    hass.async_create_task = MagicMock()
    with patch.object(
        hass.config_entries, "async_get_entry", return_value=mock_entry
    ):
        coordinator._schedule_reauth()
        coordinator._schedule_reauth()

    hass.async_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_auth_error_raises_update_failed(hass: HomeAssistant) -> None:
    """Auth errors during update raise UpdateFailed."""
    coordinator = FritzBoxVPNCoordinator(
        hass,
        {"host": MOCK_HOST, "username": "u", "password": "p"},
        None,
        None,
    )
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        side_effect=ValueError("Invalid SID")
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_connection_error_retry(hass: HomeAssistant) -> None:
    """Non-auth connection errors use retry_after on UpdateFailed."""
    coordinator = FritzBoxVPNCoordinator(
        hass,
        {"host": MOCK_HOST, "username": "u", "password": "p"},
        None,
        None,
    )
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        side_effect=ConnectionError("timeout")
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()
    assert exc_info.value.retry_after is not None
