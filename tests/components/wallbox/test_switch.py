"""Test Wallbox Switch component."""

from unittest.mock import MagicMock

from homeassistant.components.wallbox import switch


def test_wallbox_pause_class():
    """Test wallbox pause class."""

    wallbox = MagicMock()
    coordinator = MagicMock(return_value="connected")
    config = MagicMock(return_value="12345")
    name = "wallbox_pause_tester"

    wallboxPause = switch.WallboxPause(name, config, coordinator, wallbox)

    assert wallboxPause.name == "wallbox_pause_tester"
    assert wallboxPause.icon == "mdi:power-plug-off-outline"
    assert wallboxPause.available

    wallboxPause.pause_charger(True)
    wallboxPause.pause_charger(False)


def test_wallbox_updater():
    """Test wallbox pause updater."""
    station = "12345"

    wallbox = MagicMock(return_value={"key1": 5, "key2": 4})
    result = switch.wallbox_updater(wallbox, station)
    assert result
