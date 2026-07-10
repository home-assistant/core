"""Tests for the DD-WRT router client."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
import requests

from homeassistant.components.ddwrt.router import DdWrtConnectionError, DdWrtRouter

_MAC_PHONE = "AA:BB:CC:DD:EE:FF"
_MAC_LAPTOP = "11:22:33:44:55:66"

_WIRELESS_RESPONSE = (
    "{active_wireless::"
    "'AA:BB:CC:DD:EE:FF','eth1','5','54M',"
    "'11:22:33:44:55:66','eth1','2','54M'}"
)
_LAN_RESPONSE = (
    "{arp_table::"
    "'my-phone','192.168.1.100','AA:BB:CC:DD:EE:FF','5',"
    "'my-laptop','192.168.1.101','11:22:33:44:55:66','3'}"
    "{dhcp_leases::"
    "'my-phone','192.168.1.100','AA:BB:CC:DD:EE:FF','86400','1',"
    "'my-laptop','192.168.1.101','11:22:33:44:55:66','86400','2'}"
)


def _mock_response(status_code: HTTPStatus, text: str) -> MagicMock:
    """Build a mocked requests response."""
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    return response


def _make_router(*, wireless_only: bool = True) -> DdWrtRouter:
    """Build a router client for tests."""
    return DdWrtRouter(
        "192.168.1.1",
        "admin",
        "password",
        use_ssl=False,
        verify_ssl=True,
        wireless_only=wireless_only,
    )


@patch("homeassistant.components.ddwrt.router.requests.get")
def test_get_clients_wireless_only(mock_get: MagicMock) -> None:
    """Test that wireless clients are parsed and enriched with lease data."""

    def _side_effect(url: str, **kwargs: object) -> MagicMock:
        text = _WIRELESS_RESPONSE if "Wireless" in url else _LAN_RESPONSE
        return _mock_response(HTTPStatus.OK, text)

    mock_get.side_effect = _side_effect

    clients = _make_router().get_clients()

    assert clients == {
        _MAC_PHONE: {"hostname": "my-phone", "ip": "192.168.1.100"},
        _MAC_LAPTOP: {"hostname": "my-laptop", "ip": "192.168.1.101"},
    }


@patch("homeassistant.components.ddwrt.router.requests.get")
def test_get_clients_lan_mode(mock_get: MagicMock) -> None:
    """Test that all ARP-table clients are tracked when not wireless-only."""
    mock_get.return_value = _mock_response(HTTPStatus.OK, _LAN_RESPONSE)

    clients = _make_router(wireless_only=False).get_clients()

    assert set(clients) == {_MAC_PHONE, _MAC_LAPTOP}
    assert clients[_MAC_PHONE] == {"hostname": "my-phone", "ip": "192.168.1.100"}


@patch("homeassistant.components.ddwrt.router.requests.get")
def test_get_clients_without_leases(mock_get: MagicMock) -> None:
    """Test clients without a matching DHCP lease get null hostname and ip."""

    def _side_effect(url: str, **kwargs: object) -> MagicMock:
        text = _WIRELESS_RESPONSE if "Wireless" in url else "{dhcp_leases::}"
        return _mock_response(HTTPStatus.OK, text)

    mock_get.side_effect = _side_effect

    clients = _make_router().get_clients()

    assert clients == {
        _MAC_PHONE: {"hostname": None, "ip": None},
        _MAC_LAPTOP: {"hostname": None, "ip": None},
    }


@patch("homeassistant.components.ddwrt.router.requests.get")
def test_timeout_raises(mock_get: MagicMock) -> None:
    """Test a request timeout is translated to a connection error."""
    mock_get.side_effect = requests.exceptions.Timeout

    with pytest.raises(DdWrtConnectionError):
        _make_router().get_clients()


@pytest.mark.parametrize(
    "status_code",
    [HTTPStatus.UNAUTHORIZED, HTTPStatus.INTERNAL_SERVER_ERROR],
)
@patch("homeassistant.components.ddwrt.router.requests.get")
def test_bad_status_raises(mock_get: MagicMock, status_code: HTTPStatus) -> None:
    """Test non-OK status codes are translated to a connection error."""
    mock_get.return_value = _mock_response(status_code, "")

    with pytest.raises(DdWrtConnectionError):
        _make_router().get_clients()
