"""Tests for the Broadlink integration."""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from homeassistant.components.broadlink.const import DOMAIN

from tests.common import MockConfigEntry

# Do not edit/remove. Adding is ok.
BROADLINK_DEVICES = {
    "Entrance": (
        "192.168.0.11",
        "34ea34befc25",
        "RM mini 3",
        "Broadlink",
        "RM2",
        0x2737,
        57,
        8,
    ),
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
    "Garage": (
        "192.168.0.14",
        "34ea34c43f31",
        "RM4 pro",
        "Broadlink",
        "RM4",
        0x6026,
        52,
        4,
    ),
    "Bedroom": (
        "192.168.0.15",
        "34ea34b45d2c",
        "e-Sensor",
        "Broadlink",
        "A1",
        0x2714,
        20025,
        5,
    ),
    "Kitchen": (  # Not supported.
        "192.168.0.64",
        "34ea34b61d2c",
        "LB1",
        "Broadlink",
        "SmartBulb",
        0x504E,
        57,
        5,
    ),
    "Garden": (
        "192.168.1.14",
        "34ea34b44e2c",
        "MP1-1K3S2U",
        "Broadlink",
        "MP1",
        0x4F65,
        20025,
        5,
    ),
    "Rooftop": (
        "192.168.1.15",
        "34ea34b44e2d",
        "SP2",
        "Broadlink",
        "SP2",
        0x7530,
        20025,
        5,
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

    async def setup_entry(
        self, hass, mock_api=None, mock_entry=None, mock_discovery=None
    ):
        """Set up the device."""
        mock_entry = mock_entry or self.get_mock_entry()
        mock_entry.add_to_hass(hass)

        with self.patch_setup(mock_api, mock_discovery) as (mock_api, mock_discovery):
            await hass.config_entries.async_setup(mock_entry.entry_id)
            await hass.async_block_till_done()

        return mock_api, mock_entry, mock_discovery

    @contextmanager
    def patch_setup(self, mock_api=None, mock_discovery=None):
        """Patch device setup."""
        mock_api = mock_api or self.get_mock_api()
        mock_discovery = mock_discovery or self.get_mock_discovery(mock_api)

        with patch(
            "homeassistant.components.broadlink.device.blk.gendevice",
            return_value=mock_api,
        ), patch_discovery(mock_discovery) as mock_discovery:
            yield mock_api, mock_discovery

    def get_mock_discovery(self, mock_api=None):
        """Return a mock discovery."""
        mock_api = mock_api or self.get_mock_api()
        broadcast_addr = mock_api.host[0].split(".")
        broadcast_addr[3] = "255"
        broadcast_addr = ".".join(broadcast_addr)
        return [(broadcast_addr, [mock_api])]

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

    def get_discovery_info(self):
        """Return discovery data."""
        return {
            "host": self.host,
            "mac": self.mac,
            "type": self.devtype,
            "name": self.name,
            "lock": False,
        }


def get_device(name):
    """Get a device by name."""
    return BroadlinkDevice(name, *BROADLINK_DEVICES[name])


@contextmanager
def patch_discovery(mock_discovery):
    """Patch device discovery."""
    broadcast_addrs = [bd_addr for bd_addr, _ in mock_discovery]
    return_values = [iter(dev_list) for _, dev_list in mock_discovery]

    with patch(
        "homeassistant.components.broadlink.get_broadcast_addrs",
        return_value=broadcast_addrs,
    ), patch(
        "homeassistant.components.broadlink.discovery.blk.xdiscover",
        side_effect=return_values,
    ) as mock_discovery:
        yield mock_discovery
