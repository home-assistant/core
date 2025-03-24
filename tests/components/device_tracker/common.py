"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.device_tracker import (
    ATTR_ATTRIBUTES,
    ATTR_BATTERY,
    ATTR_DEV_ID,
    ATTR_GPS,
    ATTR_GPS_ACCURACY,
    ATTR_HOST_NAME,
    ATTR_LOCATION_NAME,
    ATTR_MAC,
    DOMAIN,
    SERVICE_SEE,
    DeviceScanner,
    ScannerEntity,
    SourceType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType, GPSType
from homeassistant.loader import bind_hass

from tests.common import MockPlatform, mock_platform


@callback
@bind_hass
def async_see(
    hass: HomeAssistant,
    mac: str | None = None,
    dev_id: str | None = None,
    host_name: str | None = None,
    location_name: str | None = None,
    gps: GPSType | None = None,
    gps_accuracy=None,
    battery: int | None = None,
    attributes: dict | None = None,
):
    """Call service to notify you see device."""
    data = {
        key: value
        for key, value in (
            (ATTR_MAC, mac),
            (ATTR_DEV_ID, dev_id),
            (ATTR_HOST_NAME, host_name),
            (ATTR_LOCATION_NAME, location_name),
            (ATTR_GPS, gps),
            (ATTR_GPS_ACCURACY, gps_accuracy),
            (ATTR_BATTERY, battery),
        )
        if value is not None
    }
    if attributes:
        data[ATTR_ATTRIBUTES] = attributes
    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_SEE, data))


class MockScannerEntity(ScannerEntity):
    """Test implementation of a ScannerEntity."""

    def __init__(self) -> None:
        """Init."""
        self.connected = False
        self._hostname = "test.hostname.org"
        self._ip_address = "0.0.0.0"
        self._mac_address = "ad:de:ef:be:ed:fe"

    @property
    def source_type(self) -> SourceType:
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
        self.async_write_ha_state()


class MockScanner(DeviceScanner):
    """Mock device scanner."""

    def __init__(self) -> None:
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


def mock_legacy_device_tracker_setup(
    hass: HomeAssistant, legacy_device_scanner: MockScanner
) -> None:
    """Mock legacy device tracker platform setup."""

    async def _async_get_scanner(
        hass: HomeAssistant, config: ConfigType
    ) -> MockScanner:
        """Return the test scanner."""
        return legacy_device_scanner

    mocked_platform = MockPlatform()
    mocked_platform.async_get_scanner = _async_get_scanner
    mock_platform(hass, "test.device_tracker", mocked_platform)
