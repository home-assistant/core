"""Test test fixture configuration."""
import socket

import pytest
import pytest_socket

from homeassistant.core import async_get_hass


def test_sockets_disabled():
    """Test we can't open sockets."""
    with pytest.raises(pytest_socket.SocketBlockedError):
        socket.socket()


def test_sockets_enabled(socket_enabled):
    """Test we can't connect to an address different from 127.0.0.1."""
    mysocket = socket.socket()
    with pytest.raises(pytest_socket.SocketConnectBlockedError):
        mysocket.connect(("127.0.0.2", 1234))


async def test_hass_cv(hass):
    """Test hass context variable.

    When tests are using the `hass`, this tests that the hass context variable was set
    in the fixture and that async_get_hass() works correctly.
    """
    assert async_get_hass() is hass
