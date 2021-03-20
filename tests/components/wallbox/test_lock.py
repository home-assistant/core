"""Test Wallbox Lock Component."""

from unittest.mock import MagicMock

from homeassistant.components.wallbox import lock


def test_wallbox_lock_class():
    """Test Wallbox Lock class."""

    wallbox = MagicMock()
    coordinator = MagicMock(return_value="connected")
    config = MagicMock(return_value="12345")
    name = "wallbox_pause_tester"

    wallboxLock = lock.WallboxLock(name, config, coordinator, wallbox)

    assert wallboxLock.name == "wallbox_pause_tester"
    assert wallboxLock.icon == "mdi:lock"
    assert wallboxLock.available

    wallboxLock.lock_charger(True)
    wallboxLock.lock_charger(False)


def test_wallbox_updater():
    """Test wallbox lock updater."""
    station = "12345"

    wallbox = MagicMock(return_value={"key1": 5, "key2": 4})
    result = lock.wallbox_updater(wallbox, station)
    assert result
