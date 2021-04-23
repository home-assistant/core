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
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_COMFORT,
    PRESET_ECO,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.fritzbox.const import (
    ATTR_STATE_BATTERY_LOW,
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_HOLIDAY_MODE,
    ATTR_STATE_LOCKED,
    ATTR_STATE_SUMMER_MODE,
    ATTR_STATE_WINDOW_OPEN,
    DOMAIN as FB_DOMAIN,
)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import MOCK_CONFIG, FritzDeviceClimateMock

from tests.common import async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.fake_name"


async def setup_fritzbox(hass: HomeAssistant, config: dict):
    """Set up mock AVM Fritz!Box."""
    assert await async_setup_component(hass, FB_DOMAIN, config) is True
    await hass.async_block_till_done()


async def test_setup(hass: HomeAssistant, fritz: Mock):
    """Test setup of platform."""
    device = FritzDeviceClimateMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.attributes[ATTR_BATTERY_LEVEL] == 23
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 18
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake_name"
    assert state.attributes[ATTR_HVAC_MODES] == [HVAC_MODE_HEAT, HVAC_MODE_OFF]
    assert state.attributes[ATTR_MAX_TEMP] == 28
    assert state.attributes[ATTR_MIN_TEMP] == 8
    assert state.attributes[ATTR_PRESET_MODE] is None
    assert state.attributes[ATTR_PRESET_MODES] == [PRESET_ECO, PRESET_COMFORT]
    assert state.attributes[ATTR_STATE_BATTERY_LOW] is True
    assert state.attributes[ATTR_STATE_DEVICE_LOCKED] == "fake_locked_device"
    assert state.attributes[ATTR_STATE_HOLIDAY_MODE] == "fake_holiday"
    assert state.attributes[ATTR_STATE_LOCKED] == "fake_locked"
    assert state.attributes[ATTR_STATE_SUMMER_MODE] == "fake_summer"
    assert state.attributes[ATTR_STATE_WINDOW_OPEN] == "fake_window"
    assert state.attributes[ATTR_TEMPERATURE] == 19.5
    assert state.state == HVAC_MODE_HEAT


async def test_target_temperature_on(hass: HomeAssistant, fritz: Mock):
    """Test turn device on."""
    device = FritzDeviceClimateMock()
    fritz().get_devices.return_value = [device]
    device.target_temperature = 127.0

    await setup_fritzbox(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_TEMPERATURE] == 30


async def test_target_temperature_off(hass: HomeAssistant, fritz: Mock):
    """Test turn device on."""
    device = FritzDeviceClimateMock()
    fritz().get_devices.return_value = [device]
    device.target_temperature = 126.5

    await setup_fritzbox(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_TEMPERATURE] == 0


async def test_update(hass: HomeAssistant, fritz: Mock):
    """Test update with error."""
    device = FritzDeviceClimateMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 18
    assert state.attributes[ATTR_MAX_TEMP] == 28
    assert state.attributes[ATTR_MIN_TEMP] == 8
    assert state.attributes[ATTR_TEMPERATURE] == 19.5

    device.actual_temperature = 19
    device.target_temperature = 20

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)

    assert device.update.call_count == 2
    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 19
    assert state.attributes[ATTR_TEMPERATURE] == 20


async def test_update_error(hass: HomeAssistant, fritz: Mock):
    """Test update with error."""
    device = FritzDeviceClimateMock()
    device.update.side_effect = HTTPError("Boom")
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    assert device.update.call_count == 1
    assert fritz().login.call_count == 2

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert device.update.call_count == 2
    assert fritz().login.call_count == 4


async def test_set_temperature_temperature(hass: HomeAssistant, fritz: Mock):
    """Test setting temperature by temperature."""
    device = FritzDeviceClimateMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

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
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_HVAC_MODE: HVAC_MODE_OFF,
            ATTR_TEMPERATURE: 123,
        },
        True,
    )
    assert device.set_target_temperature.call_args_list == [call(0)]


async def test_set_temperature_mode_heat(hass: HomeAssistant, fritz: Mock):
    """Test setting temperature by mode."""
    device = FritzDeviceClimateMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_HVAC_MODE: HVAC_MODE_HEAT,
            ATTR_TEMPERATURE: 123,
        },
        True,
    )
    assert device.set_target_temperature.call_args_list == [call(22)]


async def test_set_hvac_mode_off(hass: HomeAssistant, fritz: Mock):
    """Test setting hvac mode."""
    device = FritzDeviceClimateMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVAC_MODE_OFF},
        True,
    )
    assert device.set_target_temperature.call_args_list == [call(0)]


async def test_set_hvac_mode_heat(hass: HomeAssistant, fritz: Mock):
    """Test setting hvac mode."""
    device = FritzDeviceClimateMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        True,
    )
    assert device.set_target_temperature.call_args_list == [call(22)]


async def test_set_preset_mode_comfort(hass: HomeAssistant, fritz: Mock):
    """Test setting preset mode."""
    device = FritzDeviceClimateMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

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
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

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
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.attributes[ATTR_PRESET_MODE] is None

    device.target_temperature = 98

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)

    assert device.update.call_count == 2
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_COMFORT

    device.target_temperature = 99

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)

    assert device.update.call_count == 3
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_ECO
