"""Tests for shared entity helpers."""

from unittest.mock import MagicMock

from custom_components.fritzbox_vpn.const import UNIQUE_ID_SUFFIX_SWITCH
from custom_components.fritzbox_vpn.entity import (
    connection_available,
    connection_data,
    vpn_device_info,
    vpn_switch_attributes,
    vpn_unique_id,
)

from tests.fixtures import MOCK_VPN_CONNECTIONS


def test_vpn_unique_id() -> None:
    """Unique ID combines prefix, connection UID, and suffix."""
    assert vpn_unique_id("abc", UNIQUE_ID_SUFFIX_SWITCH) == "fritzbox_vpn_abc_switch"


def test_connection_available_and_data() -> None:
    """Availability follows coordinator success and UID membership."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = MOCK_VPN_CONNECTIONS
    assert connection_available(coordinator, "conn-abc") is True
    assert connection_data(coordinator, "missing") is None


def test_vpn_switch_attributes() -> None:
    """Switch attributes include status from coordinator."""
    coordinator = MagicMock()
    coordinator.data = MOCK_VPN_CONNECTIONS
    coordinator.get_vpn_status = MagicMock(return_value="enabled")
    attrs = vpn_switch_attributes(coordinator, "conn-abc")
    assert attrs["name"] == "Office VPN"
    assert attrs["status"] == "enabled"


def test_vpn_device_info() -> None:
    """Device info uses connection name and entry identifiers."""
    entry = MagicMock()
    entry.entry_id = "entry-1"
    info = vpn_device_info(entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"])
    assert info["name"] == "Office VPN"
