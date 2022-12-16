"""Tests for VeSync common utilities."""

from unittest.mock import MagicMock

from homeassistant.components.vesync.common import async_process_devices


async def test_async_process_devices_fans(hass):
    """Test when air purifiers are processed."""
    manager = MagicMock()

    fan = MagicMock()
    del fan.set_humidity

    manager.fans = [fan]

    devices = await async_process_devices(hass, manager)

    assert devices == {
        "fans": [fan],
        "humidifiers": [],
        "lights": [],
        "sensors": [fan],
        "switches": [],
    }


async def test_async_process_devices_humidifiers(hass):
    """Test when humidifiers are processed."""
    manager = MagicMock()

    humidifier = MagicMock()
    humidifier.set_humidity.return_value = True

    manager.fans = [humidifier]

    devices = await async_process_devices(hass, manager)

    assert devices == {
        "fans": [],
        "humidifiers": [humidifier],
        "lights": [],
        "sensors": [humidifier],
        "switches": [],
    }


async def test_async_process_devices_lights(hass):
    """Test when light bulbs are processed."""
    manager = MagicMock()

    bulb = MagicMock()

    manager.bulbs = [bulb]

    devices = await async_process_devices(hass, manager)

    assert devices == {
        "fans": [],
        "humidifiers": [],
        "lights": [bulb],
        "sensors": [],
        "switches": [],
    }


async def test_async_process_devices_switches(hass):
    """Test when wall switches are processed."""
    manager = MagicMock()

    outlet = MagicMock()

    manager.outlets = [outlet]

    devices = await async_process_devices(hass, manager)

    assert devices == {
        "fans": [],
        "humidifiers": [],
        "lights": [],
        "sensors": [outlet],
        "switches": [outlet],
    }


async def test_async_process_devices_outlets(hass):
    """Test when wall outlets are processed."""
    manager = MagicMock()

    outlet = MagicMock()
    outlet.is_dimmable.return_value = False

    light = MagicMock()
    light.is_dimmable.return_value = True

    manager.switches = [outlet, light]

    devices = await async_process_devices(hass, manager)

    assert devices == {
        "fans": [],
        "humidifiers": [],
        "lights": [light],
        "sensors": [],
        "switches": [outlet],
    }
