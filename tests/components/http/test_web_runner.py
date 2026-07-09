"""Tests for the HTTP web runner socket helpers."""

from collections.abc import Callable
import socket
from unittest.mock import patch

import pytest

from homeassistant.components.http.web_runner import create_server_sockets

pytestmark = pytest.mark.usefixtures("socket_enabled")


def test_create_server_sockets_binds(
    unused_tcp_port_factory: Callable[[], int],
) -> None:
    """Test sockets are created and bound but not listening yet."""
    port = unused_tcp_port_factory()

    sockets = create_server_sockets(["127.0.0.1"], port)

    assert len(sockets) == 1
    assert sockets[0].getsockname() == ("127.0.0.1", port)
    # The port is claimed: a second bind of the same address fails.
    other = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(OSError):
        other.bind(("127.0.0.1", port))
    other.close()
    for sock in sockets:
        sock.close()


def test_create_server_sockets_address_in_use(
    unused_tcp_port_factory: Callable[[], int],
) -> None:
    """Test a port that is already in use raises OSError."""
    port = unused_tcp_port_factory()
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", port))
    blocker.listen(1)

    with pytest.raises(OSError, match="error while attempting to bind on address"):
        create_server_sockets(["127.0.0.1"], port)

    blocker.close()


def test_create_server_sockets_unresolvable_host() -> None:
    """Test an unresolvable host raises before any socket is bound."""
    with (
        patch(
            "socket.getaddrinfo",
            side_effect=socket.gaierror(socket.EAI_NONAME, "Name or service not known"),
        ),
        pytest.raises(socket.gaierror),
    ):
        create_server_sockets(["name-does-not-resolve.invalid"], 8123)


def test_create_server_sockets_dual_stack(
    unused_tcp_port_factory: Callable[[], int],
) -> None:
    """Test the default dual-stack bind creates one socket per family."""
    if not socket.has_ipv6:
        pytest.skip("IPv6 not supported on this system")
    port = unused_tcp_port_factory()

    sockets = create_server_sockets(["0.0.0.0", "::"], port)

    assert {sock.family for sock in sockets} == {socket.AF_INET, socket.AF_INET6}
    for sock in sockets:
        sock.close()
