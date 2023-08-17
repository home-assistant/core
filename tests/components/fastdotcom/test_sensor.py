"""Tests for the Fast.com sensor."""
from unittest.mock import MagicMock

from homeassistant.components.fastdotcom.sensor import SpeedtestSensor
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


async def test_speedtest_sensor() -> None:
    """Test the Fast.com sensor."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.data = 50.0

    hass = MagicMock(spec=HomeAssistant)
    hass.data = {"fastdotcom": coordinator}

    sensor = SpeedtestSensor(coordinator)
    sensor.hass = hass

    assert sensor.name == "Fast.com Download"
    assert sensor.device_class == "data_rate"
    assert sensor.native_unit_of_measurement == "Mbit/s"
    assert sensor.state == 50.0
