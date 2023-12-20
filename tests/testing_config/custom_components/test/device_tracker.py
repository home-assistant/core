"""Provide a mock device scanner."""

from homeassistant.components.device_tracker import DeviceScanner
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SourceType


async def async_get_scanner(hass, config):
    """Return a mock scanner."""
    return SCANNER


class MockScannerEntity(ScannerEntity):
    """Test implementation of a ScannerEntity."""

    def __init__(self):
        """Init."""
        self.connected = False
        self._hostname = "test.hostname.org"
        self._ip_address = "0.0.0.0"
        self._mac_address = "ad:de:ef:be:ed:fe"

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SourceType.ROUTER

    @property
    def battery_level(self):
        """Return the battery level of the device.

        Percentage from 0-100.
        """
        return 100

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self._ip_address

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._mac_address

    @property
    def hostname(self) -> str:
        """Return hostname of the device."""
        return self._hostname

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return self.connected

    def set_connected(self):
        """Set connected to True."""
        self.connected = True
        self.async_schedule_update_ha_state()


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the config entry."""
    entity = MockScannerEntity()
    async_add_entities([entity])


class MockScanner(DeviceScanner):
    """Mock device scanner."""

    def __init__(self):
        """Initialize the MockScanner."""
        self.devices_home = []

    def come_home(self, device):
        """Make a device come home."""
        self.devices_home.append(device)

    def leave_home(self, device):
        """Make a device leave the house."""
        self.devices_home.remove(device)

    def reset(self):
        """Reset which devices are home."""
        self.devices_home = []

    def scan_devices(self):
        """Return a list of fake devices."""
        return list(self.devices_home)

    def get_device_name(self, device):
        """Return a name for a mock device.

        Return None for dev1 for testing.
        """
        return None if device == "DEV1" else device.lower()


SCANNER = MockScanner()
