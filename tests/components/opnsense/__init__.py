"""Tests for the opnsense component."""

from homeassistant.components.opnsense.const import (
    CONF_API_SECRET,
    CONF_TRACKER_INTERFACE,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
)

from tests.async_mock import MagicMock

TITLE = "OPNsense"
CONFIG_DATA = {
    CONF_HOST: "router.lan",
    CONF_PORT: 80,
    CONF_API_KEY: "key",
    CONF_API_SECRET: "secret",
    CONF_SSL: False,
    CONF_VERIFY_SSL: False,
    CONF_TRACKER_INTERFACE: "LAN",
}
CONFIG_DATA_IMPORT = {
    CONF_URL: "http://router.lan/api",
    CONF_API_KEY: "key",
    CONF_API_SECRET: "secret",
    CONF_VERIFY_SSL: False,
    CONF_TRACKER_INTERFACE: ["LAN"],
}

ARP = [
    {
        "hostname": "",
        "intf": "igb1",
        "intf_description": "LAN",
        "ip": "192.168.0.123",
        "mac": "ff:ff:ff:ff:ff:ff",
        "manufacturer": "",
    },
    {
        "hostname": "Desktop",
        "intf": "igb1",
        "intf_description": "LAN",
        "ip": "192.168.0.167",
        "mac": "ff:ff:ff:ff:ff:fe",
        "manufacturer": "OEM",
    },
]
INTERFACES = {"igb0": "WAN", "igb1": "LAN"}


def setup_mock_diagnostics(mock_diagnostics):
    """Prepare mock diagnostics results."""
    interface_client = MagicMock()
    mock_diagnostics.InterfaceClient.return_value = interface_client
    interface_client.get_arp.return_value = ARP

    network_insight_client = MagicMock()
    mock_diagnostics.NetworkInsightClient.return_value = network_insight_client
    network_insight_client.get_interfaces.return_value = INTERFACES

    return mock_diagnostics
