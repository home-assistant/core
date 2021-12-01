"""Standard fixtures for the Fjäråskupan integration."""
from __future__ import annotations

from unittest.mock import patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData, BaseBleakScanner
from pytest import fixture


@fixture(name="scanner", autouse=True)
def fixture_scanner(hass):
    """Fixture for scanner."""

    devices = [BLEDevice("1.1.1.1", "COOKERHOOD_FJAR")]

    class MockScanner(BaseBleakScanner):
        """Mock Scanner."""

        async def start(self):
            """Start scanning for devices."""
            for device in devices:
                self._callback(device, AdvertisementData())

        async def stop(self):
            """Stop scanning for devices."""

        @property
        def discovered_devices(self) -> list[BLEDevice]:
            """Return discovered devices."""
            return devices

        def set_scanning_filter(self, **kwargs):
            """Set the scanning filter."""

    with patch(
        "homeassistant.components.fjaraskupan.config_flow.BleakScanner", new=MockScanner
    ), patch(
        "homeassistant.components.fjaraskupan.config_flow.CONST_WAIT_TIME", new=0.01
    ):
        yield devices
