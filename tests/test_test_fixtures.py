"""Test test fixture configuration."""
import socket

import pytest
import pytest_socket


def test_sockets_disabled():
    """Test we can't open sockets."""
    with pytest.raises(pytest_socket.SocketBlockedError):
        socket.socket()


def test_sockets_enabled(socket_enabled):
    """Test we can't connect to an address different from 127.0.0.1."""
    mysocket = socket.socket()
    with pytest.raises(pytest_socket.SocketConnectBlockedError):
        mysocket.connect(("127.0.0.2", 1234))
