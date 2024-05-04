"""Tests for EQ3 Max! component."""

from unittest.mock import create_autospec, patch

from maxcube.device import MAX_DEVICE_MODE_AUTOMATIC, MAX_DEVICE_MODE_MANUAL
from maxcube.room import MaxRoom
from maxcube.thermostat import MaxThermostat
from maxcube.wallthermostat import MaxWallThermostat
from maxcube.windowshutter import MaxWindowShutter
import pytest

from homeassistant.components.maxcube import DOMAIN
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import now


@pytest.fixture
def room():
    """Create a test MAX! room."""
    r = MaxRoom()
    r.id = 1
    r.name = "TestRoom"
    return r


@pytest.fixture
def thermostat():
    """Create test MAX! thermostat."""
    t = create_autospec(MaxThermostat)
    t.name = "TestThermostat"
    t.serial = "AABBCCDD01"
    t.rf_address = "abc1"
    t.room_id = 1
    t.is_thermostat.return_value = True
    t.is_wallthermostat.return_value = False
    t.is_windowshutter.return_value = False
    t.mode = MAX_DEVICE_MODE_AUTOMATIC
    t.comfort_temperature = 19.0
    t.eco_temperature = 14.0
    t.target_temperature = 20.5
    t.actual_temperature = 19.0
    t.max_temperature = None
    t.min_temperature = None
    t.valve_position = 25  # 25%
    t.battery = 1
    return t


@pytest.fixture
def wallthermostat():
    """Create test MAX! wall thermostat."""
    t = create_autospec(MaxWallThermostat)
    t.name = "TestWallThermostat"
    t.serial = "AABBCCDD02"
    t.rf_address = "abc2"
    t.room_id = 1
    t.is_thermostat.return_value = False
    t.is_wallthermostat.return_value = True
    t.is_windowshutter.return_value = False
    t.mode = MAX_DEVICE_MODE_MANUAL
    t.comfort_temperature = 19.0
    t.eco_temperature = 14.0
    t.target_temperature = 4.5
    t.actual_temperature = 19.0
    t.max_temperature = 29.0
    t.min_temperature = 4.5
    t.battery = 1
    return t


@pytest.fixture
def windowshutter():
    """Create test MAX! window shutter."""
    shutter = create_autospec(MaxWindowShutter)
    shutter.name = "TestShutter"
    shutter.serial = "AABBCCDD03"
    shutter.rf_address = "abc3"
    shutter.room_id = 1
    shutter.is_open = True
    shutter.is_thermostat.return_value = False
    shutter.is_wallthermostat.return_value = False
    shutter.is_windowshutter.return_value = True
    shutter.battery = 1
    return shutter


@pytest.fixture
def hass_config():
    """Return test HASS configuration."""
    return {
        DOMAIN: {
            "gateways": [
                {
                    "host": "1.2.3.4",
                }
            ]
        }
    }


@pytest.fixture
async def cube(hass, hass_config, room, thermostat, wallthermostat, windowshutter):
    """Build and setup a cube mock with a single room and some devices."""
    with patch("homeassistant.components.maxcube.MaxCube") as mock:
        cube = mock.return_value
        cube.rooms = [room]
        cube.devices = [thermostat, wallthermostat, windowshutter]
        cube.room_by_id.return_value = room
        cube.devices_by_room.return_value = [thermostat, wallthermostat, windowshutter]
        assert await async_setup_component(hass, DOMAIN, hass_config)
        await hass.async_block_till_done()
        gateway = hass_config[DOMAIN]["gateways"][0]
        mock.assert_called_with(gateway["host"], gateway.get("port", 62910), now=now)
        return cube
