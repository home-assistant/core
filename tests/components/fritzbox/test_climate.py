"""Tests for AVM Fritz!Box climate component."""
from datetime import timedelta
from unittest.mock import Mock, call

from requests.exceptions import HTTPError

from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN,
    PRESET_COMFORT,
    PRESET_ECO,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.fritzbox.const import (
    ATTR_STATE_BATTERY_LOW,
    ATTR_STATE_HOLIDAY_MODE,
    ATTR_STATE_SUMMER_MODE,
    ATTR_STATE_WINDOW_OPEN,
    DOMAIN as FB_DOMAIN,
)
from homeassistant.components.sensor import ATTR_STATE_CLASS, DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_DEVICES,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import FritzDeviceClimateMock, setup_config_entry
from .const import CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.{CONF_FAKE_NAME}"


async def test_setup(hass: HomeAssistant, fritz: Mock):
    """Test setup of platform."""
    device = FritzDeviceClimateMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_BATTERY_LEVEL] == 23
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 18
    assert state.attributes[ATTR_FRIENDLY_NAME] == CONF_FAKE_NAME
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.HEAT, HVACMode.OFF]
    assert state.attributes[ATTR_MAX_TEMP] == 28
    assert state.attributes[ATTR_MIN_TEMP] == 8
    assert state.attributes[ATTR_PRESET_MODE] is None
    assert state.attributes[ATTR_PRESET_MODES] == [PRESET_ECO, PRESET_COMFORT]
    assert state.attributes[ATTR_STATE_BATTERY_LOW] is True
    assert state.attributes[ATTR_STATE_HOLIDAY_MODE] == "fake_holiday"
    assert state.attributes[ATTR_STATE_SUMMER_MODE] == "fake_summer"
    assert state.attributes[ATTR_STATE_WINDOW_OPEN] == "fake_window"
    assert state.attributes[ATTR_TEMPERATURE] == 19.5
    assert ATTR_STATE_CLASS not in state.attributes
    assert state.state == HVACMode.HEAT

    state = hass.states.get(f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_battery")
    assert state
    assert state.state == "23"
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{CONF_FAKE_NAME} Battery"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert ATTR_STATE_CLASS not in state.attributes

    state = hass.states.get(f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_comfort_temperature")
    assert state
    assert state.state == "22.0"
    assert (
        state.attributes[ATTR_FRIENDLY_NAME] == f"{CONF_FAKE_NAME} Comfort Temperature"
    )
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS
    assert ATTR_STATE_CLASS not in state.attributes

    state = hass.states.get(f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_eco_temperature")
    assert state
    assert state.state == "16.0"
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{CONF_FAKE_NAME} Eco Temperature"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS
    assert ATTR_STATE_CLASS not in state.attributes

    state = hass.states.get(
        f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_next_scheduled_temperature"
    )
    assert state
    assert state.state == "22.0"
    assert (
        state.attributes[ATTR_FRIENDLY_NAME]
        == f"{CONF_FAKE_NAME} Next Scheduled Temperature"
    )
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS
    assert ATTR_STATE_CLASS not in state.attributes

    state = hass.states.get(
        f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_next_scheduled_change_time"
    )
    assert state
    assert state.state == "1970-01-01T00:00:00+00:00"
    assert (
        state.attributes[ATTR_FRIENDLY_NAME]
        == f"{CONF_FAKE_NAME} Next Scheduled Change Time"
    )
    assert ATTR_STATE_CLASS not in state.attributes

    state = hass.states.get(f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_next_scheduled_preset")
    assert state
    assert state.state == PRESET_COMFORT
    assert (
        state.attributes[ATTR_FRIENDLY_NAME]
        == f"{CONF_FAKE_NAME} Next Scheduled Preset"
    )
    assert ATTR_STATE_CLASS not in state.attributes

    state = hass.states.get(
        f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_current_scheduled_preset"
    )
    assert state
    assert state.state == PRESET_ECO
    assert (
        state.attributes[ATTR_FRIENDLY_NAME]
        == f"{CONF_FAKE_NAME} Current Scheduled Preset"
    )
    assert ATTR_STATE_CLASS not in state.attributes


async def test_target_temperature_on(hass: HomeAssistant, fritz: Mock):
    """Test turn device on."""
    device = FritzDeviceClimateMock()
    device.target_temperature = 127.0
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_TEMPERATURE] == 30


async def test_target_temperature_off(hass: HomeAssistant, fritz: Mock):
    """Test turn device on."""
    device = FritzDeviceClimateMock()
    device.target_temperature = 126.5
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_TEMPERATURE] == 0


async def test_update(hass: HomeAssistant, fritz: Mock):
    """Test update without error."""
    device = FritzDeviceClimateMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 18
    assert state.attributes[ATTR_MAX_TEMP] == 28
    assert state.attributes[ATTR_MIN_TEMP] == 8
    assert state.attributes[ATTR_TEMPERATURE] == 19.5

    device.temperature = 19
    device.target_temperature = 20

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)

    assert fritz().update_devices.call_count == 2
    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 19
    assert state.attributes[ATTR_TEMPERATURE] == 20


async def test_automatic_offset(hass: HomeAssistant, fritz: Mock):
    """Test when automatic offset is configured on fritz!box device."""
    device = FritzDeviceClimateMock()
    device.temperature = 18
    device.actual_temperature = 19
    device.target_temperature = 20
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 18
    assert state.attributes[ATTR_MAX_TEMP] == 28
    assert state.attributes[ATTR_MIN_TEMP] == 8
    assert state.attributes[ATTR_TEMPERATURE] == 20


async def test_update_error(hass: HomeAssistant, fritz: Mock):
    """Test update with error."""
    device = FritzDeviceClimateMock()
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


async def test_set_temperature_temperature(hass: HomeAssistant, fritz: Mock):
    """Test setting temperature by temperature."""
    device = FritzDeviceClimateMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 123},
        True,
    )
    assert device.set_target_temperature.call_args_list == [call(123)]


async def test_set_temperature_mode_off(hass: HomeAssistant, fritz: Mock):
    """Test setting temperature by mode."""
    device = FritzDeviceClimateMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_HVAC_MODE: HVACMode.OFF,
            ATTR_TEMPERATURE: 123,
        },
        True,
    )
    assert device.set_target_temperature.call_args_list == [call(0)]


async def test_set_temperature_mode_heat(hass: HomeAssistant, fritz: Mock):
    """Test setting temperature by mode."""
    device = FritzDeviceClimateMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_HVAC_MODE: HVACMode.HEAT,
            ATTR_TEMPERATURE: 123,
        },
        True,
    )
    assert device.set_target_temperature.call_args_list == [call(22)]


async def test_set_hvac_mode_off(hass: HomeAssistant, fritz: Mock):
    """Test setting hvac mode."""
    device = FritzDeviceClimateMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        True,
    )
    assert device.set_target_temperature.call_args_list == [call(0)]


async def test_set_hvac_mode_heat(hass: HomeAssistant, fritz: Mock):
    """Test setting hvac mode."""
    device = FritzDeviceClimateMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        True,
    )
    assert device.set_target_temperature.call_args_list == [call(22)]


async def test_set_preset_mode_comfort(hass: HomeAssistant, fritz: Mock):
    """Test setting preset mode."""
    device = FritzDeviceClimateMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_COMFORT},
        True,
    )
    assert device.set_target_temperature.call_args_list == [call(22)]


async def test_set_preset_mode_eco(hass: HomeAssistant, fritz: Mock):
    """Test setting preset mode."""
    device = FritzDeviceClimateMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_ECO},
        True,
    )
    assert device.set_target_temperature.call_args_list == [call(16)]


async def test_preset_mode_update(hass: HomeAssistant, fritz: Mock):
    """Test preset mode."""
    device = FritzDeviceClimateMock()
    device.comfort_temperature = 98
    device.eco_temperature = 99
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_PRESET_MODE] is None

    device.target_temperature = 98

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)

    assert fritz().update_devices.call_count == 2
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_COMFORT

    device.target_temperature = 99

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)

    assert fritz().update_devices.call_count == 3
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_ECO
