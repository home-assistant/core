"""The tests for the opnsense device tracker platform."""

from unittest import mock

from homeassistant.components.opnsense.device_tracker import OPNsenseDeviceScanner


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
