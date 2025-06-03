"""Tests for the Network Configuration integration."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, _patch, patch

import ifaddr
import pytest

from . import LOOPBACK_IPADDR, NO_LOOPBACK_IPADDR


def _generate_mock_adapters():
    mock_lo0 = Mock(spec=ifaddr.Adapter)
    mock_lo0.nice_name = "lo0"
    mock_lo0.ips = [ifaddr.IP(LOOPBACK_IPADDR, 8, "lo0")]
    mock_lo0.index = 0
    mock_eth0 = Mock(spec=ifaddr.Adapter)
    mock_eth0.nice_name = "eth0"
    mock_eth0.ips = [ifaddr.IP(("2001:db8::", 1, 1), 8, "eth0")]
    mock_eth0.index = 1
    mock_eth1 = Mock(spec=ifaddr.Adapter)
    mock_eth1.nice_name = "eth1"
    mock_eth1.ips = [ifaddr.IP(NO_LOOPBACK_IPADDR, 23, "eth1")]
    mock_eth1.index = 2
    mock_vtun0 = Mock(spec=ifaddr.Adapter)
    mock_vtun0.nice_name = "vtun0"
    mock_vtun0.ips = [ifaddr.IP("169.254.3.2", 16, "vtun0")]
    mock_vtun0.index = 3
    return [mock_eth0, mock_lo0, mock_eth1, mock_vtun0]


def _mock_socket(sockname: list[str]) -> Generator[None]:
    """Mock the network socket."""
    with patch(
        "homeassistant.components.network.util.socket.socket",
        return_value=MagicMock(getsockname=Mock(return_value=sockname)),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_network() -> Generator[None]:
    """Override mock of network util's async_get_adapters."""
    with patch(
        "homeassistant.components.network.util.ifaddr.get_adapters",
        return_value=_generate_mock_adapters(),
    ):
        yield


@pytest.fixture(autouse=True)
def override_mock_get_source_ip(
    mock_get_source_ip: _patch,
) -> Generator[None]:
    """Override mock of network util's async_get_source_ip."""
    mock_get_source_ip.stop()
    yield
    mock_get_source_ip.start()


@pytest.fixture
def mock_socket(request: pytest.FixtureRequest) -> Generator[None]:
    """Mock the network socket."""
    yield from _mock_socket(request.param)


@pytest.fixture
def mock_socket_loopback() -> Generator[None]:
    """Mock the network socket with loopback address."""
    yield from _mock_socket([LOOPBACK_IPADDR])


@pytest.fixture
def mock_socket_no_loopback() -> Generator[None]:
    """Mock the network socket with loopback address."""
    yield from _mock_socket([NO_LOOPBACK_IPADDR])
