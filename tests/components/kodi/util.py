"""Test the Kodi config flow."""

from ipaddress import ip_address

from homeassistant.components import zeroconf
from homeassistant.components.kodi.const import DEFAULT_SSL

TEST_HOST = {
    "host": "1.1.1.1",
    "port": 8080,
    "ssl": DEFAULT_SSL,
}

TEST_CREDENTIALS = {"username": "username", "password": "password"}


TEST_WS_PORT = {"ws_port": 9090}

UUID = "11111111-1111-1111-1111-111111111111"
TEST_DISCOVERY = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    port=8080,
    hostname="hostname.local.",
    type="_xbmc-jsonrpc-h._tcp.local.",
    name="hostname._xbmc-jsonrpc-h._tcp.local.",
    properties={"uuid": UUID},
)


TEST_DISCOVERY_WO_UUID = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    port=8080,
    hostname="hostname.local.",
    type="_xbmc-jsonrpc-h._tcp.local.",
    name="hostname._xbmc-jsonrpc-h._tcp.local.",
    properties={},
)


TEST_IMPORT = {
    "name": "name",
    "host": "1.1.1.1",
    "port": 8080,
    "ws_port": 9090,
    "username": "username",
    "password": "password",
    "ssl": True,
    "timeout": 7,
}


def get_kodi_connection(
    host, port, ws_port, username, password, ssl=False, timeout=5, session=None
):
    """Get Kodi connection."""
    if ws_port is None:
        return MockConnection()
    return MockWSConnection()


class MockConnection:
    """A mock kodi connection."""

    def __init__(self, connected=True):
        """Mock the Kodi connection."""
        self._connected = connected

    async def connect(self):
        """Mock connect."""

    @property
    def connected(self):
        """Mock connected."""
        return self._connected

    @property
    def can_subscribe(self):
        """Mock can_subscribe."""
        return False

    async def close(self):
        """Mock close."""

    @property
    def server(self):
        """Mock server."""
        return None


class MockWSConnection:
    """A mock kodi websocket connection."""

    def __init__(self, connected=True):
        """Mock the websocket connection."""
        self._connected = connected

    async def connect(self):
        """Mock connect."""

    @property
    def connected(self):
        """Mock connected."""
        return self._connected

    @property
    def can_subscribe(self):
        """Mock can_subscribe."""
        return False

    async def close(self):
        """Mock close."""

    @property
    def server(self):
        """Mock server."""
        return None
