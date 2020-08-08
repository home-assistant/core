"""Tests for the Broadlink integration."""
from homeassistant.components.broadlink.const import DOMAIN

from tests.async_mock import MagicMock
from tests.common import MockConfigEntry


class BroadlinkDevice:
    """Representation of a Broadlink device."""

    def __init__(self, name, host, mac, devtype, timeout):
        """Initialize the device."""
        self.name: str = name
        self.host: str = host
        self.mac: str = mac
        self.devtype: int = devtype
        self.timeout: int = timeout

    def get_mock_api(self):
        """Return a mock device (API)."""
        mock_api = MagicMock()
        mock_api.name = self.name
        mock_api.host = (self.host, 80)
        mock_api.mac = bytes.fromhex(self.mac)
        mock_api.devtype = self.devtype
        mock_api.timeout = self.timeout
        mock_api.is_locked = False
        mock_api.auth.return_value = True
        return mock_api

    def get_mock_entry(self):
        """Return a mock config entry."""
        return MockConfigEntry(
            domain=DOMAIN,
            unique_id=self.mac,
            title=self.name,
            data=self.get_entry_data(),
        )

    def get_entry_data(self):
        """Return entry data."""
        return {
            "host": self.host,
            "mac": self.mac,
            "type": self.devtype,
            "timeout": self.timeout,
        }


def pick_device(index):
    """Pick a device."""
    devices = (
        ("Living Room", "192.168.0.32", "34ea34b45d2c", 0x2714, 5),
        ("Office", "192.168.0.64", "34ea34b43b5a", 0x5F36, 10),
    )
    return BroadlinkDevice(*devices[index])
