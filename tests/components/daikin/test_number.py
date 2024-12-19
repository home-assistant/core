"""The tests for the Daikin zone temperature control."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.daikin.number import DaikinZoneTemperature
from homeassistant.exceptions import HomeAssistantError


@pytest.fixture
def daikin_api():
    """Fixture to configure the mock Daikin device with zones and device information."""
    api = MagicMock()
    api.device.zones = [
        ["Living Room", "-", 22],
        ["Kitchen", "-", 18],
    ]
    api.device.target_temperature = 20
    api.device.mac = "00:11:22:33:44:55"
    api.device_info = {"name": "Daikin AC"}
    api.device.set_zone = AsyncMock()
    api.async_update = AsyncMock()
    return api


def test_device_without_zones(daikin_api):
    """Where device does not have zones, don't display zone temperature control."""
    daikin_api.device.zones = None
    with pytest.raises(TypeError):
        DaikinZoneTemperature(daikin_api, 0)


def test_device_with_zones_but_no_temperature_control(daikin_api):
    """Where device has zones but no zone temperature control, don't display zone temperature control."""
    daikin_api.device.zones = [["Living Room", "-", 0], ["Bedroom", "-", 0]]
    with pytest.raises(IndexError):
        DaikinZoneTemperature(daikin_api, 0)


def test_device_with_zones_and_temperature_control(daikin_api):
    """Where device has zone temperature control, check variables are correct."""
    zone_temp = DaikinZoneTemperature(daikin_api, 0)
    assert zone_temp.native_value == 22
    assert zone_temp._attr_name == "Living Room temperature"
    assert zone_temp._attr_native_min_value == 18
    assert zone_temp._attr_native_max_value == 22


@pytest.mark.asyncio
async def test_set_native_value(daikin_api):
    """Where device has zone temperature control, check temperature change of zone is working."""
    zone_temp = DaikinZoneTemperature(daikin_api, 0)

    await zone_temp.async_set_native_value(21)
    daikin_api.device.set_zone.assert_called_with(0, "lztemp_h", "21")
    daikin_api.device.zones[0][2] = 21
    await zone_temp.async_update()
    assert zone_temp.native_value == 21


@pytest.mark.asyncio
async def test_set_native_value_out_of_range(daikin_api):
    """Where device has zone temperature control, check temperature value cannot exceed max value."""
    zone_temp = DaikinZoneTemperature(daikin_api, 0)
    with pytest.raises(HomeAssistantError):
        await zone_temp.async_set_native_value(25)


if __name__ == "__main__":
    pytest.main()
