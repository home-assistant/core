"""Provide a mock device scanner."""

from homeassistant.components.device_tracker import DeviceScanner


def get_scanner(hass, config):
    """Return a mock scanner."""
    return SCANNER


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
        return None if device == 'DEV1' else device.lower()


SCANNER = MockScanner()
