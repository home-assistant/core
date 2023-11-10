"""Test test fixture configuration."""
import socket

import pytest
import pytest_socket

from homeassistant.core import HomeAssistant, async_get_hass


def test_sockets_disabled() -> None:
    """Test we can't open sockets not in allowed_hosts."""
    mysocket = socket.socket()
    with pytest.raises(pytest_socket.SocketConnectBlockedError):
        mysocket.connect(("127.0.0.2", 1234))


def test_sockets_enabled(socket_enabled) -> None:
    """Test we can open sockets to any address."""
    mysocket = socket.socket()
    with pytest.raises(ConnectionRefusedError):
        mysocket.connect(("127.0.0.2", 1234))


def test_sockets_allowed_hosts_config() -> None:
    """Test we can try to connect to 127.0.0.1."""
    mysocket = socket.socket()
    with pytest.raises(ConnectionRefusedError):
        mysocket.connect(("127.0.0.1", 1234))


@pytest.mark.allow_hosts(["127.0.0.2"])
def test_sockets_allowed_hosts_mark() -> None:
    """Test we can try to connect to an address specified in the mark."""
    mysocket = socket.socket()
    with pytest.raises(ConnectionRefusedError):
        mysocket.connect(("127.0.0.2", 1234))
    # And that the mark has overridden the config
    with pytest.raises(pytest_socket.SocketConnectBlockedError):
        mysocket.connect(("127.0.0.1", 1234))


async def test_hass_cv(hass: HomeAssistant) -> None:
    """Test hass context variable.

    When tests are using the `hass`, this tests that the hass context variable was set
    in the fixture and that async_get_hass() works correctly.
    """
    assert async_get_hass() is hass
