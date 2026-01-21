"""Test code shared between test files."""

from unittest.mock import MagicMock

from aioasuswrt.asuswrt import Device as LegacyDevice
from asusrouter.modules.client import ConnectionState

from homeassistant.components.asuswrt.const import (
    CONF_SSH_KEY,
    MODE_ROUTER,
    PROTOCOL_HTTP,
    PROTOCOL_HTTPS,
    PROTOCOL_SSH,
    PROTOCOL_TELNET,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)

ASUSWRT_BASE = "homeassistant.components.asuswrt"

HOST = "myrouter.asuswrt.com"
ROUTER_MAC_ADDR = "a1:b2:c3:d4:e5:f6"

CONFIG_DATA_TELNET = {
    CONF_HOST: HOST,
    CONF_PORT: 23,
    CONF_PROTOCOL: PROTOCOL_TELNET,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pwd",
    CONF_MODE: MODE_ROUTER,
}

CONFIG_DATA_SSH = {
    CONF_HOST: HOST,
    CONF_PORT: 22,
    CONF_PROTOCOL: PROTOCOL_SSH,
    CONF_USERNAME: "user",
    CONF_SSH_KEY: "aaaaa",
    CONF_MODE: MODE_ROUTER,
}

CONFIG_DATA_HTTP = {
    CONF_HOST: HOST,
    CONF_PORT: 80,
    CONF_PROTOCOL: PROTOCOL_HTTPS,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pwd",
}

MOCK_MACS = [
    "A1:B1:C1:D1:E1:F1",
    "A2:B2:C2:D2:E2:F2",
    "A3:B3:C3:D3:E3:F3",
    "A4:B4:C4:D4:E4:F4",
]


def make_client(mac, ip, name, node):
    """Create a modern mock client."""
    connection = MagicMock()
    connection.ip_address = ip
    connection.node = node
    description = MagicMock()
    description.name = name
    description.mac = mac
    client = MagicMock()
    client.connection = connection
    client.description = description
    client.state = ConnectionState.CONNECTED
    return client


def new_device(protocol, mac, ip, name, node=None):
    """Return a new device for specific protocol."""
    if protocol in [PROTOCOL_HTTP, PROTOCOL_HTTPS]:
        return make_client(mac, ip, name, node)
    return LegacyDevice(mac, ip, name)
