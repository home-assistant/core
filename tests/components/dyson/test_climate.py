"""Test the Dyson fan component."""

from typing import Type

from libpurecool.const import (
    AutoMode,
    FanPower,
    FanSpeed,
    FanState,
    FocusMode,
    HeatMode,
    HeatState,
)
from libpurecool.dyson_device import DysonDevice
from libpurecool.dyson_pure_hotcool import DysonPureHotCool
from libpurecool.dyson_pure_hotcool_link import DysonPureHotCoolLink
from libpurecool.dyson_pure_state import DysonPureHotCoolState
from libpurecool.dyson_pure_state_v2 import DysonPureHotCoolV2State
import pytest

from homeassistant.components.climate import DOMAIN as PLATFORM_DOMAIN
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
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_FOCUS,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.dyson.climate import (
    SUPPORT_FAN,
    SUPPORT_FAN_PCOOL,
    SUPPORT_FLAGS,
    SUPPORT_HVAC,
    SUPPORT_HVAC_PCOOL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry

from .common import (
    ENTITY_NAME,
    NAME,
    SERIAL,
    async_get_basic_device,
    async_update_device,
)

ENTITY_ID = f"{PLATFORM_DOMAIN}.{ENTITY_NAME}"


@callback
def async_get_device(spec: Type[DysonDevice]) -> DysonDevice:
    """Return a Dyson climate device."""
    device = async_get_basic_device(spec)
    device.state.heat_target = 2900
    device.environmental_state.temperature = 275
    device.environmental_state.humidity = 50
    if spec == DysonPureHotCoolLink:
        device.state.heat_mode = HeatMode.HEAT_ON.value
        device.state.heat_state = HeatState.HEAT_STATE_ON.value
        device.state.focus_mode = FocusMode.FOCUS_ON.value
    else:
        device.state.fan_power = FanPower.POWER_ON.value
        device.state.heat_mode = HeatMode.HEAT_ON.value
        device.state.heat_state = HeatState.HEAT_STATE_ON.value
        device.state.auto_mode = AutoMode.AUTO_ON.value
        device.state.fan_state = FanState.FAN_OFF.value
        device.state.speed = FanSpeed.FAN_SPEED_AUTO.value
    return device


@pytest.mark.parametrize(
    "device", [DysonPureHotCoolLink, DysonPureHotCool], indirect=True
)
async def test_state_common(hass: HomeAssistant, device: DysonDevice) -> None:
    """Test common state and attributes of two types of climate entities."""
    er = await entity_registry.async_get_registry(hass)
    assert er.async_get(ENTITY_ID).unique_id == SERIAL

    state = hass.states.get(ENTITY_ID)
    assert state.name == NAME
    attributes = state.attributes
    assert attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_FLAGS
    assert attributes[ATTR_CURRENT_TEMPERATURE] == 2
    assert attributes[ATTR_CURRENT_HUMIDITY] == 50
    assert attributes[ATTR_TEMPERATURE] == 17
    assert attributes[ATTR_MIN_TEMP] == 1
    assert attributes[ATTR_MAX_TEMP] == 37

    device.state.heat_target = 2800
    device.environmental_state.temperature = 0
    device.environmental_state.humidity = 0
    await async_update_device(
        hass,
        device,
        DysonPureHotCoolState
        if isinstance(device, DysonPureHotCoolLink)
        else DysonPureHotCoolV2State,
    )
    attributes = hass.states.get(ENTITY_ID).attributes
    assert attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert ATTR_CURRENT_HUMIDITY not in attributes
    assert attributes[ATTR_TEMPERATURE] == 7


@pytest.mark.parametrize("device", [DysonPureHotCoolLink], indirect=True)
async def test_state_purehotcoollink(
    hass: HomeAssistant, device: DysonPureHotCoolLink
) -> None:
    """Test common state and attributes of a PureHotCoolLink entity."""
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_HEAT
    attributes = state.attributes
    assert attributes[ATTR_HVAC_MODES] == SUPPORT_HVAC
    assert attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT
    assert attributes[ATTR_FAN_MODE] == FAN_FOCUS
    assert attributes[ATTR_FAN_MODES] == SUPPORT_FAN

    device.state.heat_state = HeatState.HEAT_STATE_OFF.value
    device.state.focus_mode = FocusMode.FOCUS_OFF
    await async_update_device(hass, device, DysonPureHotCoolState)
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_HEAT
    attributes = state.attributes
    assert attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE
    assert attributes[ATTR_FAN_MODE] == FAN_DIFFUSE

    device.state.heat_mode = HeatMode.HEAT_OFF.value
    await async_update_device(hass, device, DysonPureHotCoolState)
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_COOL
    attributes = state.attributes
    assert attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL


@pytest.mark.parametrize("device", [DysonPureHotCool], indirect=True)
async def test_state_purehotcool(hass: HomeAssistant, device: DysonPureHotCool) -> None:
    """Test common state and attributes of a PureHotCool entity."""
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_HEAT
    attributes = state.attributes
    assert attributes[ATTR_HVAC_MODES] == SUPPORT_HVAC_PCOOL
    assert attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT
    assert attributes[ATTR_FAN_MODE] == FAN_AUTO
    assert attributes[ATTR_FAN_MODES] == SUPPORT_FAN_PCOOL

    device.state.heat_state = HeatState.HEAT_STATE_OFF.value
    device.state.auto_mode = AutoMode.AUTO_OFF.value
    await async_update_device(hass, device, DysonPureHotCoolV2State)
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_HEAT
    attributes = state.attributes
    assert attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE
    assert attributes[ATTR_FAN_MODE] == FAN_OFF

    device.state.heat_mode = HeatMode.HEAT_OFF.value
    device.state.fan_state = FanState.FAN_ON.value
    device.state.speed = FanSpeed.FAN_SPEED_1.value
    await async_update_device(hass, device, DysonPureHotCoolV2State)
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_COOL
    attributes = state.attributes
    assert attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL
    assert attributes[ATTR_FAN_MODE] == FAN_LOW

    device.state.fan_power = FanPower.POWER_OFF.value
    await async_update_device(hass, device, DysonPureHotCoolV2State)
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_OFF
    attributes = state.attributes
    assert attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF


@pytest.mark.parametrize(
    "service,service_data,configuration_data",
    [
        (
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: -5},
            {"heat_target": "2740", "heat_mode": HeatMode.HEAT_ON},
        ),
        (
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 40},
            {"heat_target": "3100", "heat_mode": HeatMode.HEAT_ON},
        ),
        (
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 20},
            {"heat_target": "2930", "heat_mode": HeatMode.HEAT_ON},
        ),
        (
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_FOCUS},
            {"focus_mode": FocusMode.FOCUS_ON},
        ),
        (
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_DIFFUSE},
            {"focus_mode": FocusMode.FOCUS_OFF},
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVAC_MODE_HEAT},
            {"heat_mode": HeatMode.HEAT_ON},
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVAC_MODE_COOL},
            {"heat_mode": HeatMode.HEAT_OFF},
        ),
    ],
)
@pytest.mark.parametrize("device", [DysonPureHotCoolLink], indirect=True)
async def test_commands_purehotcoollink(
    hass: HomeAssistant,
    device: DysonPureHotCoolLink,
    service: str,
    service_data: dict,
    configuration_data: dict,
) -> None:
    """Test sending commands to a PureHotCoolLink entity."""
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            **service_data,
        },
        blocking=True,
    )
    device.set_configuration.assert_called_once_with(**configuration_data)


@pytest.mark.parametrize(
    "service,service_data,command,command_args",
    [
        (SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 20}, "set_heat_target", ["2930"]),
        (SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: FAN_OFF}, "turn_off", []),
        (
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_LOW},
            "set_fan_speed",
            [FanSpeed.FAN_SPEED_4],
        ),
        (
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_MEDIUM},
            "set_fan_speed",
            [FanSpeed.FAN_SPEED_7],
        ),
        (
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_HIGH},
            "set_fan_speed",
            [FanSpeed.FAN_SPEED_10],
        ),
        (SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: FAN_AUTO}, "enable_auto_mode", []),
        (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVAC_MODE_OFF}, "turn_off", []),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVAC_MODE_HEAT},
            "enable_heat_mode",
            [],
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVAC_MODE_COOL},
            "disable_heat_mode",
            [],
        ),
    ],
)
@pytest.mark.parametrize("device", [DysonPureHotCool], indirect=True)
async def test_commands_purehotcool(
    hass: HomeAssistant,
    device: DysonPureHotCoolLink,
    service: str,
    service_data: dict,
    command: str,
    command_args: list,
) -> None:
    """Test sending commands to a PureHotCool entity."""
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            **service_data,
        },
        blocking=True,
    )
    getattr(device, command).assert_called_once_with(*command_args)


@pytest.mark.parametrize("hvac_mode", [HVAC_MODE_HEAT, HVAC_MODE_COOL])
@pytest.mark.parametrize(
    "fan_power,turn_on_call_count",
    [
        (FanPower.POWER_ON.value, 0),
        (FanPower.POWER_OFF.value, 1),
    ],
)
@pytest.mark.parametrize("device", [DysonPureHotCool], indirect=True)
async def test_set_hvac_mode_purehotcool(
    hass: HomeAssistant,
    device: DysonPureHotCoolLink,
    hvac_mode: str,
    fan_power: str,
    turn_on_call_count: int,
) -> None:
    """Test setting HVAC mode of a PureHotCool entity turns on the device when it's off."""
    device.state.fan_power = fan_power
    await async_update_device(hass, device)
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_HVAC_MODE: hvac_mode,
        },
        blocking=True,
    )
    assert device.turn_on.call_count == turn_on_call_count
