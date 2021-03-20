"""Test Wallbox Number component."""

from unittest.mock import MagicMock

from homeassistant.components.wallbox import number


def test_wallbox_number_class():
    """Test wallbox number class."""

    wallbox = MagicMock()
    coordinator = MagicMock(return_value="connected")
    config = MagicMock(return_value="12345")
    name = "wallbox_pause_tester"

    wallbox_max_charging_current = number.WallboxMaxChargingCurrent(
        name, config, coordinator, wallbox
    )

    assert wallbox_max_charging_current.name == "wallbox_pause_tester"
    assert wallbox_max_charging_current.icon == "mdi:ev-station"
    assert wallbox_max_charging_current.available

    wallbox_max_charging_current.set_max_charging_current(25)


def test_wallbox_updater():
    """Test wallbox number updater."""
    station = "12345"

    wallbox = MagicMock(return_value={"key1": 5, "key2": 4})
    result = number.wallbox_updater(wallbox, station)
    assert result
