"""Tests for the opnsense component."""

from unittest.mock import AsyncMock

from homeassistant.components.opnsense.const import (
    CONF_API_SECRET,
    CONF_TRACKER_INTERFACES,
)
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL

TITLE = "OPNsense"
CONFIG_DATA = {
    CONF_URL: "http://router.lan/api",
    CONF_API_KEY: "key",
    CONF_API_SECRET: "secret",
    CONF_VERIFY_SSL: False,
}
CONFIG_DATA_IMPORT = {
    CONF_URL: "http://router.lan/api",
    CONF_API_KEY: "key",
    CONF_API_SECRET: "secret",
    CONF_VERIFY_SSL: False,
    CONF_TRACKER_INTERFACES: ["LAN"],
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
INTERFACES = {"igb0": {"name": "WAN"}, "igb1": {"name": "LAN"}}


def setup_mock_opnsense_client(mock_opnsense_client: AsyncMock) -> None:
    """Prepare mock OPNsense client results."""
    mock_instance = mock_opnsense_client.return_value
    mock_instance.get_host_firmware_version.return_value = "25.7.8"
    mock_instance.validate.return_value = None
    mock_instance.get_arp_table.return_value = ARP
    mock_instance.get_interfaces.return_value = INTERFACES
