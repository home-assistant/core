"""Test Wallbox Switch component."""

from unittest.mock import MagicMock

from homeassistant.components.wallbox import sensor


def test_wallbox_sensor_class():
    """Test wallbox pause class."""

    coordinator = MagicMock(return_value="connected")
    config = MagicMock(return_value="wallbox")
    idx = 1
    ent = "charging_power"

    wallboxSensor = sensor.WallboxSensor(coordinator, idx, ent, config)

    assert wallboxSensor.icon == "mdi:ev-station"
    assert wallboxSensor.unit_of_measurement == "kW"


def test_wallbox_updater():
    """Test wallbox pause updater."""
    station = "12345"

    wallbox = MagicMock(return_value={"key1": 5, "key2": 4})
    sensor.wallbox_updater(wallbox, station)
