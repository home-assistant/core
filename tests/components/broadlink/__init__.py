"""Tests for the Broadlink integration."""
from homeassistant.components.broadlink.const import DOMAIN

from tests.async_mock import MagicMock
from tests.common import MockConfigEntry

# Do not edit/remove. Adding is ok.
BROADLINK_DEVICES = {
    "Living Room": (
        "192.168.0.12",
        "34ea34b43b5a",
        "RM mini 3",
        "Broadlink",
        "RM4",
        0x5F36,
        44017,
        10,
    ),
    "Office": (
        "192.168.0.13",
        "34ea34b43d22",
        "RM pro",
        "Broadlink",
        "RM2",
        0x2787,
        20025,
        7,
    ),
}


class BroadlinkDevice:
    """Representation of a Broadlink device."""

    def __init__(
        self, name, host, mac, model, manufacturer, type_, devtype, fwversion, timeout
    ):
        """Initialize the device."""
        self.name: str = name
        self.host: str = host
        self.mac: str = mac
        self.model: str = model
        self.manufacturer: str = manufacturer
        self.type: str = type_
        self.devtype: int = devtype
        self.timeout: int = timeout
        self.fwversion: int = fwversion

    def get_mock_api(self):
        """Return a mock device (API)."""
        mock_api = MagicMock()
        mock_api.name = self.name
        mock_api.host = (self.host, 80)
        mock_api.mac = bytes.fromhex(self.mac)
        mock_api.model = self.model
        mock_api.manufacturer = self.manufacturer
        mock_api.type = self.type
        mock_api.devtype = self.devtype
        mock_api.timeout = self.timeout
        mock_api.is_locked = False
        mock_api.auth.return_value = True
        mock_api.get_fwversion.return_value = self.fwversion
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


def get_device(name):
    """Get a device by name."""
    return BroadlinkDevice(name, *BROADLINK_DEVICES[name])
