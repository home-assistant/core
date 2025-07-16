"""Common fixtures for the Grid connect tests."""

from collections.abc import Generator
from contextlib import ExitStack
import importlib
import socket
import types
from unittest.mock import AsyncMock, patch

import pytest


# Patch socket.socket and socket.socketpair at import time to prevent real socket usage before any test or fixture runs.
class DummySocket:
    """A dummy socket class to prevent real socket usage in tests."""

    def __init__(self, *args, **kwargs):
        """Initialize the dummy socket."""
    def close(self):
        """Close the dummy socket."""
    def setsockopt(self, *a, **k):
        """Set socket options (no-op)."""
    def bind(self, *a, **k):
        """Bind the dummy socket (no-op)."""
    def listen(self, *a, **k):
        """Listen on the dummy socket (no-op)."""
    def accept(self, *a, **k):
        """Accept a connection (returns self and dummy address)."""
        return (self, ('0.0.0.0', 0))
    def connect(self, *a, **k):
        """Connect the dummy socket (no-op)."""
    def setblocking(self, *a, **k):
        """Set blocking mode (no-op)."""
    def shutdown(self, *a, **k):
        """Shutdown the dummy socket (no-op)."""
    def fileno(self):
        """Get the file descriptor (returns 0)."""
        return 0
    def getsockname(self):
        """Get socket name (returns dummy address)."""
        return ('0.0.0.0', 0)
    def getpeername(self):
        """Get peer name (returns dummy address)."""
        return ('0.0.0.0', 0)
    def recv(self, *a, **k):
        """Receive data (returns empty bytes)."""
        return b''
    def send(self, *a, **k):
        """Send data (returns 0)."""
        return 0
    def sendall(self, *a, **k):
        """Send all data (no-op)."""
    def recvfrom(self, *a, **k):
        """Receive data from (returns empty bytes and dummy address)."""
        return (b'', ('0.0.0.0', 0))
    def sendto(self, *a, **k):
        """Send data to (returns 0)."""
        return 0

def dummy_socketpair(*args, **kwargs):
    """Create a pair of dummy sockets."""
    s1 = DummySocket()
    s2 = DummySocket()
    return (s1, s2)

socket.socket = DummySocket
socket.socketpair = dummy_socketpair

@pytest.fixture(autouse=True)
def mock_zeroconf(monkeypatch):
    """Mock zeroconf to prevent real socket usage."""
    monkeypatch.setattr("zeroconf.Zeroconf", lambda *a, **kw: types.SimpleNamespace(close=lambda: None))

@pytest.fixture(autouse=True)
def mock_bluetooth():
    """Auto-mock BLE libraries (bleak, habluetooth) to prevent real BLE/socket usage in tests."""
    patches = []
    # Patch BleakClient if bleak is used
    ble_wifi_spec = importlib.util.find_spec("homeassistant.components.grid_connect.ble_wifi")
    if ble_wifi_spec is not None:
        ble_wifi = importlib.import_module("homeassistant.components.grid_connect.ble_wifi")
        patches.append(patch.object(ble_wifi, "BleakClient", AsyncMock))
    # Patch habluetooth if available
    habluetooth_spec = importlib.util.find_spec("habluetooth")
    if habluetooth_spec is not None:
        patches.append(patch("habluetooth.BluetoothClient", AsyncMock))
    # Use a single with statement for all patches
    context_managers = patches if patches else [patch("builtins.object", lambda: None)]
    with ExitStack() as stack:
        for cm in context_managers:
            stack.enter_context(cm)
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.grid_connect.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
