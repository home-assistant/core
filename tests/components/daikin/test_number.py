"""The tests for the Daikin zone temperature control."""

import unittest
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.daikin.number import DaikinZoneTemperature
from homeassistant.exceptions import HomeAssistantError


class TestDaikinZoneTemperature(unittest.TestCase):
    """Test cases for supporting zone temperature control."""

    def setUp(self):
        """Configure mock device with zones and device information."""
        self.daikin_api = MagicMock()
        self.daikin_api.device.zones = [
            ["Living Room", "-", 22],
            ["Kitchen", "-", 18],
        ]
        self.daikin_api.device.target_temperature = 20
        self.daikin_api.device.mac = "00:11:22:33:44:55"
        self.daikin_api.device_info = {"name": "Daikin AC"}

    def test_device_without_zones(self):
        """Where device does not have zones, don't display zone temperature control."""
        self.daikin_api.device.zones = None
        with pytest.raises(TypeError):
            DaikinZoneTemperature(self.daikin_api, 0)

    def test_device_with_zones_but_no_temperature_control(self):
        """Where device has zones but no zone temperature control, don't display zone temperature control."""
        self.daikin_api.device.zones = [["Living Room", "-", 0], ["Bedroom", "-", 0]]
        with pytest.raises(IndexError):
            DaikinZoneTemperature(self.daikin_api, 0)

    def test_device_with_zones_and_temperature_control(self):
        """Where device has zone temperature control, check variables are correct."""
        zone_temp = DaikinZoneTemperature(self.daikin_api, 0)
        assert zone_temp.native_value == 22
        assert zone_temp._attr_name == "Living Room temperature"
        assert zone_temp._attr_native_min_value == 18
        assert zone_temp._attr_native_max_value == 22

    async def test_set_native_value(self):
        """Where device has zone temperature control, check temperature change of zone is working."""
        zone_temp = DaikinZoneTemperature(self.daikin_api, 0)
        self.daikin_api.device.set_zone = AsyncMock()
        await zone_temp.async_set_native_value(21)
        assert zone_temp.native_value == 21
        self.daikin_api.device.set_zone.assert_called_with(0, "lztemp_h", "21")

    async def test_set_native_value_out_of_range(self):
        """Where device has zone temperautre control, check temperature value cannot exceed max value."""
        zone_temp = DaikinZoneTemperature(self.daikin_api, 0)
        with pytest.raises(HomeAssistantError):
            await zone_temp.async_set_native_value(25)


if __name__ == "__main__":
    unittest.main()
