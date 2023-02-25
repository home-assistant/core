"""Tests for AVM Fritz!Box switch component."""
from datetime import timedelta
from unittest.mock import Mock

from requests.exceptions import HTTPError

from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorStateClass,
)
from homeassistant.components.switch import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_DEVICES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import FritzDeviceSwitchMock, setup_config_entry
from .const import CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.{CONF_FAKE_NAME}"


async def test_setup(hass: HomeAssistant, fritz: Mock) -> None:
    """Test setup of platform."""
    device = FritzDeviceSwitchMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_FRIENDLY_NAME] == CONF_FAKE_NAME
    assert ATTR_STATE_CLASS not in state.attributes

    state = hass.states.get(f"{ENTITY_ID}_humidity")
    assert state is None

    sensors = (
        [
            f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_temperature",
            "1.23",
            f"{CONF_FAKE_NAME} Temperature",
            UnitOfTemperature.CELSIUS,
            SensorStateClass.MEASUREMENT,
        ],
        [
            f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_power_consumption",
            "5.678",
            f"{CONF_FAKE_NAME} Power Consumption",
            UnitOfPower.WATT,
            SensorStateClass.MEASUREMENT,
        ],
        [
            f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_total_energy",
            "1.234",
            f"{CONF_FAKE_NAME} Total Energy",
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorStateClass.TOTAL_INCREASING,
        ],
        [
            f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_voltage",
            "230.0",
            f"{CONF_FAKE_NAME} Voltage",
            UnitOfElectricPotential.VOLT,
            SensorStateClass.MEASUREMENT,
        ],
        [
            f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_electric_current",
            "0.025",
            f"{CONF_FAKE_NAME} Electric Current",
            UnitOfElectricCurrent.AMPERE,
            SensorStateClass.MEASUREMENT,
        ],
    )

    for sensor in sensors:
        state = hass.states.get(sensor[0])
        assert state
        assert state.state == sensor[1]
        assert state.attributes[ATTR_FRIENDLY_NAME] == sensor[2]
        assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == sensor[3]
        assert state.attributes[ATTR_STATE_CLASS] == sensor[4]


async def test_turn_on(hass: HomeAssistant, fritz: Mock) -> None:
    """Test turn device on."""
    device = FritzDeviceSwitchMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_switch_state_on.call_count == 1


async def test_turn_off(hass: HomeAssistant, fritz: Mock) -> None:
    """Test turn device off."""
    device = FritzDeviceSwitchMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_switch_state_off.call_count == 1


async def test_update(hass: HomeAssistant, fritz: Mock) -> None:
    """Test update without error."""
    device = FritzDeviceSwitchMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert fritz().update_devices.call_count == 1
    assert fritz().login.call_count == 1

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert fritz().update_devices.call_count == 2
    assert fritz().login.call_count == 1


async def test_update_error(hass: HomeAssistant, fritz: Mock) -> None:
    """Test update with error."""
    device = FritzDeviceSwitchMock()
    fritz().update_devices.side_effect = HTTPError("Boom")
    assert not await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert fritz().update_devices.call_count == 2
    assert fritz().login.call_count == 2

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert fritz().update_devices.call_count == 4
    assert fritz().login.call_count == 4


async def test_assume_device_unavailable(hass: HomeAssistant, fritz: Mock) -> None:
    """Test assume device as unavailable."""
    device = FritzDeviceSwitchMock()
    device.voltage = 0
    device.energy = 0
    device.power = 0
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_device_current_unavailable(hass: HomeAssistant, fritz: Mock) -> None:
    """Test current in case voltage and power are not available."""
    device = FritzDeviceSwitchMock()
    device.voltage = None
    device.power = None
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON

    state = hass.states.get(f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_electric_current")
    assert state
    assert state.state == "0.0"
