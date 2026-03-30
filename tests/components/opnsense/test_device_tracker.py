"""The tests for the opnsense device tracker platform."""

from unittest import mock

from homeassistant.components.opnsense.const import (
    CONF_INTERFACE_CLIENT,
    CONF_TRACKER_INTERFACES,
    DOMAIN,
)
from homeassistant.components.opnsense.device_tracker import (
    OPNsenseDeviceScanner,
    async_get_scanner,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def test_get_scanner() -> None:
    """Test creating an OPNsense scanner and reading device data."""
    interface_client = mock.MagicMock()
    interface_client.get_arp.return_value = [
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

    scanner = OPNsenseDeviceScanner(interface_client, ["LAN"])

    assert scanner.scan_devices() == ["ff:ff:ff:ff:ff:ff", "ff:ff:ff:ff:ff:fe"]
    assert scanner.get_device_name("ff:ff:ff:ff:ff:fe") == "Desktop"
    assert scanner.get_device_name("ff:ff:ff:ff:ff:ff") is None
    assert scanner.get_device_name("ff:ff:ff:ff:ff:fd") is None
    assert scanner.get_extra_attributes("ff:ff:ff:ff:ff:ff") == {}
    assert scanner.get_extra_attributes("ff:ff:ff:ff:ff:fe") == {"manufacturer": "OEM"}
    assert scanner.get_extra_attributes("ff:ff:ff:ff:ff:fd") == {}


async def test_async_get_scanner_no_runtime_data(
    hass: HomeAssistant,
) -> None:
    """async_get_scanner returns None when no runtime_data exists."""
    scanner = await async_get_scanner(hass, {})
    assert scanner is None


async def test_async_get_scanner_with_runtime_data(hass: HomeAssistant) -> None:
    """async_get_scanner uses runtime_data from loaded OPNsense entry."""
    interface_client = mock.MagicMock()
    interface_client.get_arp.return_value = []

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.runtime_data = {
        CONF_INTERFACE_CLIENT: interface_client,
        CONF_TRACKER_INTERFACES: [],
    }
    entry.add_to_hass(hass)

    scanner = await async_get_scanner(hass, {})

    assert scanner is not None
    assert scanner.scan_devices() == []
