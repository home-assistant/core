"""Unit tests for coordinator helper functions and update edge cases."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.fritzbox_vpn.coordinator import FritzBoxVPNCoordinator
from fritzboxvpn.parsing import (
    connection_active_from_api,
    extract_box_connections_from_data,
    normalize_connection_uid,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_HOST, MOCK_VPN_CONNECTIONS


def test_connection_active_from_api_variants() -> None:
    """Active flag accepts bool, int, and string forms."""
    assert connection_active_from_api({"active": True}) is True
    assert connection_active_from_api({"activated": 1}) is True
    assert connection_active_from_api({"active": "on"}) is True
    assert connection_active_from_api({}) is False


def test_normalize_connection_uid() -> None:
    """UID normalization trims and rejects empty values."""
    assert normalize_connection_uid("  abc  ") == "abc"
    assert normalize_connection_uid("") is None
    assert normalize_connection_uid(None) is None


def test_extract_box_connections_alternate_paths() -> None:
    """Support alternate data.lua nesting for boxConnections."""
    inner_list = {
        "data": {
            "init": {
                "shareWireguard": {
                    "boxConnections": [
                        {"uid": "x", "active": 1, "name": "X"},
                    ]
                }
            }
        }
    }
    box = extract_box_connections_from_data(inner_list, "shareWireguard")
    assert box is not None

    top_level = {
        "data": {
            "boxConnections": {"y": {"uid": "y", "active": 0}},
        }
    }
    assert extract_box_connections_from_data(top_level, "shareWireguard") is not None


@pytest.mark.asyncio
async def test_coordinator_removed_vpn_triggers_callback(hass: HomeAssistant) -> None:
    """Removed VPN UIDs invoke on_orphaned_removed callback."""
    entry = MockConfigEntry(
        domain="fritzbox_vpn",
        data={"host": MOCK_HOST, "username": "u", "password": "p"},
    )
    callback = MagicMock()
    coordinator = FritzBoxVPNCoordinator(
        hass, entry.data, None, entry.entry_id, on_orphaned_removed=callback
    )
    coordinator.async_set_updated_data(dict(MOCK_VPN_CONNECTIONS))
    coordinator.fritz_session = AsyncMock()
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        return_value={"conn-abc": MOCK_VPN_CONNECTIONS["conn-abc"]}
    )

    await coordinator._async_update_data()
    callback.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_get_vpn_status_unknown(hass: HomeAssistant) -> None:
    """Unknown UID returns unknown status."""
    coordinator = FritzBoxVPNCoordinator(
        hass, {"host": MOCK_HOST, "username": "u", "password": "p"}, None, None
    )
    assert coordinator.get_vpn_status("missing") == "unknown"
