"""Test the Dyson fan component."""
import json

from libpurecool.const import (
    FanPower,
    FanSpeed,
    FanState,
    FocusMode,
    HeatMode,
    HeatState,
    HeatTarget,
)
from libpurecool.dyson_pure_hotcool import DysonPureHotCool
from libpurecool.dyson_pure_hotcool_link import DysonPureHotCoolLink
from libpurecool.dyson_pure_state import DysonPureHotCoolState
from libpurecool.dyson_pure_state_v2 import DysonPureHotCoolV2State
import pytest

from homeassistant.components.climate import (
    DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.climate.const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)
from homeassistant.components.dyson import CONF_LANGUAGE, DOMAIN as DYSON_DOMAIN
from homeassistant.components.dyson.climate import FAN_DIFFUSE, FAN_FOCUS, SUPPORT_FLAGS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    CONF_DEVICES,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_CELSIUS,
)
from homeassistant.setup import async_setup_component

from .common import load_mock_device

from tests.async_mock import Mock, call, patch


class MockDysonState(DysonPureHotCoolState):
    """Mock Dyson state."""

    # pylint: disable=super-init-not-called

    def __init__(self):
        """Create new Mock Dyson State."""

    def __repr__(self):
        """Mock repr because original one fails since constructor not called."""
        return "<MockDysonState>"


def _get_config():
    """Return a config dictionary."""
    return {
        DYSON_DOMAIN: {
            CONF_USERNAME: "email",
            CONF_PASSWORD: "password",
            CONF_LANGUAGE: "GB",
            CONF_DEVICES: [
                {"device_id": "XX-XXXXX-XX", "device_ip": "192.168.0.1"},
                {"device_id": "YY-YYYYY-YY", "device_ip": "192.168.0.2"},
            ],
        }
    }


def _get_dyson_purehotcool_device():
    """Return a valid device as provided by the Dyson web services."""
    device = Mock(spec=DysonPureHotCool)
    load_mock_device(device)
    device.name = "Living room"
    device.state.heat_target = "0000"
    device.state.heat_mode = HeatMode.HEAT_OFF.value
    device.state.fan_power = FanPower.POWER_OFF.value
    device.environmental_state.humidity = 42
    device.environmental_state.temperature = 298
    return device


def _get_device_off():
    """Return a device with state off."""
    device = Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    return device


def _get_device_cool():
    """Return a device with state of cooling."""
    device = Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    device.state.focus_mode = FocusMode.FOCUS_OFF.value
    device.state.heat_target = HeatTarget.celsius(12)
    device.state.heat_mode = HeatMode.HEAT_OFF.value
    device.state.heat_state = HeatState.HEAT_STATE_OFF.value
    return device


def _get_device_heat_on():
    """Return a device with state of heating."""
    device = Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    device.serial = "YY-YYYYY-YY"
    device.state.heat_target = HeatTarget.celsius(23)
    device.state.heat_mode = HeatMode.HEAT_ON.value
    device.state.heat_state = HeatState.HEAT_STATE_ON.value
    device.environmental_state.temperature = 289
    device.environmental_state.humidity = 53
    return device


@pytest.fixture(autouse=True)
def patch_platforms_fixture():
    """Only set up the climate platform for the climate tests."""
    with patch("homeassistant.components.dyson.DYSON_PLATFORMS", new=[DOMAIN]):
        yield


@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_device_heat_on()],
)
@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
async def test_pure_hot_cool_link_set_mode(mocked_login, mocked_devices, hass):
    """Test set climate mode."""
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()

    device = mocked_devices.return_value[0]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.temp_name", ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        True,
    )

    set_config = device.set_configuration
    assert set_config.call_args == call(heat_mode=HeatMode.HEAT_ON)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.temp_name", ATTR_HVAC_MODE: HVAC_MODE_COOL},
        True,
    )

    set_config = device.set_configuration
    assert set_config.call_args == call(heat_mode=HeatMode.HEAT_OFF)


@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_device_heat_on()],
)
@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
async def test_pure_hot_cool_link_set_fan(mocked_login, mocked_devices, hass):
    """Test set climate fan."""
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()

    device = mocked_devices.return_value[0]
    device.temp_unit = TEMP_CELSIUS

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.temp_name", ATTR_FAN_MODE: FAN_FOCUS},
        True,
    )

    set_config = device.set_configuration
    assert set_config.call_args == call(focus_mode=FocusMode.FOCUS_ON)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.temp_name", ATTR_FAN_MODE: FAN_DIFFUSE},
        True,
    )

    set_config = device.set_configuration
    assert set_config.call_args == call(focus_mode=FocusMode.FOCUS_OFF)


@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_device_heat_on()],
)
@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
async def test_pure_hot_cool_link_state(mocked_login, mocked_devices, hass):
    """Test set climate temperature."""
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()

    state = hass.states.get("climate.temp_name")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_FLAGS
    assert state.attributes[ATTR_TEMPERATURE] == 23
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 289 - 273
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 53
    assert state.state == HVAC_MODE_HEAT
    assert len(state.attributes[ATTR_HVAC_MODES]) == 2
    assert HVAC_MODE_HEAT in state.attributes[ATTR_HVAC_MODES]
    assert HVAC_MODE_COOL in state.attributes[ATTR_HVAC_MODES]
    assert len(state.attributes[ATTR_FAN_MODES]) == 2
    assert FAN_FOCUS in state.attributes[ATTR_FAN_MODES]
    assert FAN_DIFFUSE in state.attributes[ATTR_FAN_MODES]

    device = mocked_devices.return_value[0]
    update_callback = device.add_message_listener.call_args[0][0]

    device.state.focus_mode = FocusMode.FOCUS_ON.value
    await hass.async_add_executor_job(update_callback, MockDysonState())
    await hass.async_block_till_done()

    state = hass.states.get("climate.temp_name")
    assert state.attributes[ATTR_FAN_MODE] == FAN_FOCUS

    device.state.focus_mode = FocusMode.FOCUS_OFF.value
    await hass.async_add_executor_job(update_callback, MockDysonState())
    await hass.async_block_till_done()

    state = hass.states.get("climate.temp_name")
    assert state.attributes[ATTR_FAN_MODE] == FAN_DIFFUSE

    device.state.heat_mode = HeatMode.HEAT_ON.value
    device.state.heat_state = HeatState.HEAT_STATE_OFF.value
    await hass.async_add_executor_job(update_callback, MockDysonState())
    await hass.async_block_till_done()

    state = hass.states.get("climate.temp_name")
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE

    device.environmental_state.humidity = 0
    await hass.async_add_executor_job(update_callback, MockDysonState())
    await hass.async_block_till_done()

    state = hass.states.get("climate.temp_name")
    assert state.attributes.get(ATTR_CURRENT_HUMIDITY) is None

    device.environmental_state = None
    await hass.async_add_executor_job(update_callback, MockDysonState())
    await hass.async_block_till_done()

    state = hass.states.get("climate.temp_name")
    assert state.attributes.get(ATTR_CURRENT_HUMIDITY) is None

    device.state.heat_mode = HeatMode.HEAT_OFF.value
    device.state.heat_state = HeatState.HEAT_STATE_OFF.value
    await hass.async_add_executor_job(update_callback, MockDysonState())
    await hass.async_block_till_done()

    state = hass.states.get("climate.temp_name")
    assert state.state == HVAC_MODE_COOL
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL


@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[],
)
@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
async def test_setup_component_without_devices(mocked_login, mocked_devices, hass):
    """Test setup component with no devices."""
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids(DOMAIN)
    assert not entity_ids


@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_device_heat_on()],
)
@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
async def test_dyson_set_temperature(mocked_login, mocked_devices, hass):
    """Test set climate temperature."""
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()

    device = mocked_devices.return_value[0]
    device.temp_unit = TEMP_CELSIUS

    # Without correct target temp.
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.temp_name",
            ATTR_TARGET_TEMP_HIGH: 25.0,
            ATTR_TARGET_TEMP_LOW: 15.0,
        },
        True,
    )

    set_config = device.set_configuration
    assert set_config.call_count == 0

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.temp_name", ATTR_TEMPERATURE: 23},
        True,
    )

    set_config = device.set_configuration
    assert set_config.call_args == call(
        heat_mode=HeatMode.HEAT_ON, heat_target=HeatTarget.celsius(23)
    )

    # Should clip the target temperature between 1 and 37 inclusive.
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.temp_name", ATTR_TEMPERATURE: 50},
        True,
    )

    set_config = device.set_configuration
    assert set_config.call_args == call(
        heat_mode=HeatMode.HEAT_ON, heat_target=HeatTarget.celsius(37)
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.temp_name", ATTR_TEMPERATURE: -5},
        True,
    )

    set_config = device.set_configuration
    assert set_config.call_args == call(
        heat_mode=HeatMode.HEAT_ON, heat_target=HeatTarget.celsius(1)
    )


@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_device_cool()],
)
@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
async def test_dyson_set_temperature_when_cooling_mode(
    mocked_login, mocked_devices, hass
):
    """Test set climate temperature when heating is off."""
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()

    device = mocked_devices.return_value[0]
    device.temp_unit = TEMP_CELSIUS

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.temp_name", ATTR_TEMPERATURE: 23},
        True,
    )

    set_config = device.set_configuration
    assert set_config.call_args == call(
        heat_mode=HeatMode.HEAT_ON, heat_target=HeatTarget.celsius(23)
    )


@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_device_heat_on(), _get_device_cool()],
)
@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
async def test_setup_component_with_parent_discovery(
    mocked_login, mocked_devices, hass
):
    """Test setup_component using discovery."""
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids(DOMAIN)
    assert len(entity_ids) == 2


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_component_setup_only_once(devices, login, hass):
    """Test if entities are created only once."""
    config = _get_config()
    await async_setup_component(hass, DYSON_DOMAIN, config)
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids(DOMAIN)
    assert len(entity_ids) == 1
    state = hass.states.get(entity_ids[0])
    assert state.name == "Living room"


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_device_off()],
)
async def test_purehotcoollink_component_setup_only_once(devices, login, hass):
    """Test if entities are created only once."""
    config = _get_config()
    await async_setup_component(hass, DYSON_DOMAIN, config)
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids(DOMAIN)
    assert len(entity_ids) == 1
    state = hass.states.get(entity_ids[0])
    assert state.name == "Temp Name"


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_update_state(devices, login, hass):
    """Test state update."""
    device = devices.return_value[0]
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()
    event = {
        "msg": "CURRENT-STATE",
        "product-state": {
            "fpwr": "ON",
            "fdir": "OFF",
            "auto": "OFF",
            "oscs": "ON",
            "oson": "ON",
            "nmod": "OFF",
            "rhtm": "ON",
            "fnst": "FAN",
            "ercd": "11E1",
            "wacd": "NONE",
            "nmdv": "0004",
            "fnsp": "0002",
            "bril": "0002",
            "corf": "ON",
            "cflr": "0085",
            "hflr": "0095",
            "sltm": "OFF",
            "osal": "0045",
            "osau": "0095",
            "ancp": "CUST",
            "tilt": "OK",
            "hsta": "HEAT",
            "hmax": "2986",
            "hmod": "HEAT",
        },
    }
    device.state = DysonPureHotCoolV2State(json.dumps(event))
    update_callback = device.add_message_listener.call_args[0][0]

    await hass.async_add_executor_job(update_callback, device.state)
    await hass.async_block_till_done()
    state = hass.states.get("climate.living_room")
    attributes = state.attributes

    assert attributes[ATTR_TEMPERATURE] == 25
    assert attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_empty_env_attributes(devices, login, hass):
    """Test empty environmental state update."""
    device = devices.return_value[0]
    device.environmental_state.temperature = 0
    device.environmental_state.humidity = None
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room")
    attributes = state.attributes

    assert ATTR_CURRENT_HUMIDITY not in attributes


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_fan_state_off(devices, login, hass):
    """Test device fan state off."""
    device = devices.return_value[0]
    device.state.fan_state = FanState.FAN_OFF.value
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room")
    attributes = state.attributes

    assert attributes[ATTR_FAN_MODE] == FAN_OFF


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_hvac_action_cool(devices, login, hass):
    """Test device HVAC action cool."""
    device = devices.return_value[0]
    device.state.fan_power = FanPower.POWER_ON.value
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room")
    attributes = state.attributes

    assert attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_hvac_action_idle(devices, login, hass):
    """Test device HVAC action idle."""
    device = devices.return_value[0]
    device.state.fan_power = FanPower.POWER_ON.value
    device.state.heat_mode = HeatMode.HEAT_ON.value
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room")
    attributes = state.attributes

    assert attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_set_temperature(devices, login, hass):
    """Test set temperature."""
    device = devices.return_value[0]
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()
    state = hass.states.get("climate.living_room")
    attributes = state.attributes
    min_temp = attributes[ATTR_MIN_TEMP]
    max_temp = attributes[ATTR_MAX_TEMP]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.bed_room", ATTR_TEMPERATURE: 23},
        True,
    )
    device.set_heat_target.assert_not_called()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_TEMPERATURE: 23},
        True,
    )
    assert device.set_heat_target.call_count == 1
    device.set_heat_target.assert_called_with("2960")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_TEMPERATURE: min_temp - 1},
        True,
    )
    assert device.set_heat_target.call_count == 2
    device.set_heat_target.assert_called_with(HeatTarget.celsius(min_temp))

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_TEMPERATURE: max_temp + 1},
        True,
    )
    assert device.set_heat_target.call_count == 3
    device.set_heat_target.assert_called_with(HeatTarget.celsius(max_temp))


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_set_fan_mode(devices, login, hass):
    """Test set fan mode."""
    device = devices.return_value[0]
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.bed_room", ATTR_FAN_MODE: FAN_OFF},
        True,
    )
    device.turn_off.assert_not_called()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_FAN_MODE: FAN_OFF},
        True,
    )
    assert device.turn_off.call_count == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_FAN_MODE: FAN_LOW},
        True,
    )
    assert device.set_fan_speed.call_count == 1
    device.set_fan_speed.assert_called_with(FanSpeed.FAN_SPEED_4)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_FAN_MODE: FAN_MEDIUM},
        True,
    )
    assert device.set_fan_speed.call_count == 2
    device.set_fan_speed.assert_called_with(FanSpeed.FAN_SPEED_7)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_FAN_MODE: FAN_HIGH},
        True,
    )
    assert device.set_fan_speed.call_count == 3
    device.set_fan_speed.assert_called_with(FanSpeed.FAN_SPEED_10)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_FAN_MODE: FAN_AUTO},
        True,
    )
    assert device.enable_auto_mode.call_count == 1


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_set_hvac_mode(devices, login, hass):
    """Test set HVAC mode."""
    device = devices.return_value[0]
    await async_setup_component(hass, DYSON_DOMAIN, _get_config())
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.bed_room", ATTR_HVAC_MODE: HVAC_MODE_OFF},
        True,
    )
    device.turn_off.assert_not_called()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_HVAC_MODE: HVAC_MODE_OFF},
        True,
    )
    assert device.turn_off.call_count == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        True,
    )
    assert device.turn_on.call_count == 1
    assert device.enable_heat_mode.call_count == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_HVAC_MODE: HVAC_MODE_COOL},
        True,
    )
    assert device.turn_on.call_count == 2
    assert device.disable_heat_mode.call_count == 1
