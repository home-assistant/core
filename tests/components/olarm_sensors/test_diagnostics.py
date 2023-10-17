"""Diagnostics Test for Olarm Sensors."""
import unittest
from unittest.mock import MagicMock

from homeassistant.components.olarm_sensors.const import DOMAIN, VERSION
from homeassistant.components.olarm_sensors.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)
from homeassistant.helpers.device_registry import DeviceEntry


class TestOlarmDiagnostics(unittest.IsolatedAsyncioTestCase):
    """Test diagnostics."""

    async def asyncSetUp(self):
        """Set up test instance."""
        self.hass = MagicMock()  # Create a mock Home Assistant instance

    async def test_async_get_config_entry_diagnostics(self):
        """Test entry diagnostics."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "config_entry_id"
        DeviceEntry(name="All Devices")
        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["version"] == VERSION

    async def test_async_get_device_diagnostics(self):
        """Test device diagnostics."""
        hass = MagicMock()
        entry = MagicMock()
        hass.data[DOMAIN]["devices"] = {
            "scan_interval": 3600,
            "olarm_devices": ["device_id_1", "device_id_2"],
            "alarm_code": "1234",
        }
        device_entry = DeviceEntry(name="device_id_1")
        result = await async_get_device_diagnostics(hass, entry, device_entry)

        assert result["version"] == VERSION


if __name__ == "__main__":
    unittest.main()
