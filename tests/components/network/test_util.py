"""Tests for network socket utilities."""

import socket
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.network import util


@pytest.mark.parametrize(
    ("target", "family", "sockname", "expected"),
    [
        pytest.param(
            "192.168.1.20",
            socket.AF_INET,
            ("192.168.1.5", 1234),
            "192.168.1.5",
            id="ipv4",
        ),
        pytest.param(
            "example.local",
            socket.AF_INET,
            ("192.168.1.5", 1234),
            "192.168.1.5",
            id="hostname",
        ),
        pytest.param(
            "fd12::20", socket.AF_INET6, ("fd12::5", 1234, 0, 0), "fd12::5", id="ipv6"
        ),
        pytest.param(
            "fe80::20%eth0",
            socket.AF_INET6,
            ("fe80::5", 1234, 0, 2),
            "fe80::5%2",
            id="ipv6_scope",
        ),
    ],
)
def test_async_get_source_ip(
    target: str,
    family: socket.AddressFamily,
    sockname: tuple[str, int] | tuple[str, int, int, int],
    expected: str,
) -> None:
    """Select the socket family and preserve the scope of a link local source."""
    sock = MagicMock(getsockname=MagicMock(return_value=sockname))
    with patch(
        "homeassistant.components.network.util.socket.socket", return_value=sock
    ) as create_socket:
        assert util.async_get_source_ip(target) == expected

    create_socket.assert_called_once_with(family, socket.SOCK_DGRAM)
    sock.setblocking.assert_called_once_with(False)
    sock.connect.assert_called_once_with((target, 1))
    sock.close.assert_called_once_with()


@pytest.mark.parametrize(
    "target",
    [
        pytest.param("192.168.1.20", id="ipv4"),
        pytest.param("fd12::20", id="ipv6"),
    ],
)
def test_async_get_source_ip_no_route(target: str) -> None:
    """Close the socket when the target has no route."""
    sock = MagicMock(connect=MagicMock(side_effect=OSError))
    with patch(
        "homeassistant.components.network.util.socket.socket", return_value=sock
    ):
        assert util.async_get_source_ip(target) is None

    sock.close.assert_called_once_with()
