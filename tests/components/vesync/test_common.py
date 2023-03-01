"""Tests for VeSync common utilities."""

from unittest.mock import MagicMock, patch

from homeassistant.components.vesync.common import async_process_devices
from homeassistant.core import HomeAssistant


async def test_async_process_devices_fans(hass: HomeAssistant) -> None:
    """Test when air purifiers are processed."""
    fan = MagicMock()

    manager = MagicMock()
    manager.fans = [fan]

    devices = await async_process_devices(hass, manager)

    assert devices == {
        "fans": [fan],
        "humidifiers": [],
        "lights": [],
        "numbers": [],
        "sensors": [fan],
        "switches": [],
    }


async def test_async_process_devices_humidifiers(hass: HomeAssistant) -> None:
    """Test when humidifiers are processed."""
    humidifier1 = MagicMock()
    humidifier1.night_light = True
    humidifier2 = MagicMock()
    humidifier2.night_light = False

    manager = MagicMock()
    manager.fans = [humidifier1, humidifier2]

    with patch(
        "homeassistant.components.vesync.common.is_humidifier"
    ) as mock_is_humidifier:
        mock_is_humidifier.return_value = True
        devices = await async_process_devices(hass, manager)

    assert devices == {
        "fans": [],
        "humidifiers": [humidifier1, humidifier2],
        "lights": [humidifier1],
        "numbers": [humidifier1, humidifier2],
        "sensors": [humidifier1, humidifier2],
        "switches": [humidifier1, humidifier2],
    }


async def test_async_process_devices_lights(hass: HomeAssistant) -> None:
    """Test when light bulbs are processed."""
    bulb = MagicMock()

    manager = MagicMock()
    manager.bulbs = [bulb]

    devices = await async_process_devices(hass, manager)

    assert devices == {
        "fans": [],
        "humidifiers": [],
        "lights": [bulb],
        "numbers": [],
        "sensors": [],
        "switches": [],
    }


async def test_async_process_devices_switches(hass: HomeAssistant) -> None:
    """Test when wall switches are processed."""
    outlet = MagicMock()

    manager = MagicMock()
    manager.outlets = [outlet]

    devices = await async_process_devices(hass, manager)

    assert devices == {
        "fans": [],
        "humidifiers": [],
        "lights": [],
        "numbers": [],
        "sensors": [outlet],
        "switches": [outlet],
    }


async def test_async_process_devices_outlets(hass: HomeAssistant) -> None:
    """Test when wall outlets are processed."""
    outlet = MagicMock()
    outlet.is_dimmable.return_value = False

    light = MagicMock()
    light.is_dimmable.return_value = True

    manager = MagicMock()
    manager.switches = [outlet, light]

    devices = await async_process_devices(hass, manager)

    assert devices == {
        "fans": [],
        "humidifiers": [],
        "lights": [light],
        "numbers": [],
        "sensors": [],
        "switches": [outlet],
    }
