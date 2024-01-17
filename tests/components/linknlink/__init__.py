"""Tests for the LinknLnk integration."""
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from homeassistant.components.linknlink.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

LINKNLINK_DEVICES = {
    "Living Room": (
        "192.168.2.12",
        "ec0b12a43ba1",
        "eHub",
        "LinknLink",
        "EHUB",
        0x520B,
        44017,
        10,
    ),
    "Bedroom": (
        "192.168.2.15",
        "ec0b12a43bb2",
        "eTHS",
        "LinknLink",
        "ETHS",
        0xAC7C,
        20025,
        5,
    ),
    "Office": (  # Not supported.
        "192.168.2.64",
        "ec0b12a43bc3",
        "eMotion",
        "LinknLink",
        "EMOTION",
        0xAC7B,
        57,
        5,
    ),
    "Kitchen": (  # Not supported.
        "192.168.2.64",
        "ec0b12a43bc3",
        "eMotion2",
        "LinknLink",
        "EMOTION2",
        0x7777,
        57,
        5,
    ),
}


@dataclass
class MockSetup:
    """Representation of a mock setup."""

    api: MagicMock
    entry: MockConfigEntry
    factory: MagicMock


class LinknLinkDevice:
    """Representation of a LinknLink device."""

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

    async def setup_entry(self, hass: HomeAssistant, mock_api=None, mock_entry=None):
        """Set up the device."""
        mock_api = mock_api or self.get_mock_api()
        mock_entry = mock_entry or self.get_mock_entry()
        mock_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.linknlink.device.llk.gendevice",
            return_value=mock_api,
        ) as mock_factory:
            await hass.config_entries.async_setup(mock_entry.entry_id)
            await hass.async_block_till_done()

        return MockSetup(mock_api, mock_entry, mock_factory)

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
    return LinknLinkDevice(name, *LINKNLINK_DEVICES[name])
