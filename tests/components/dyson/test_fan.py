"""Test the Dyson fan component."""
from typing import Type

from libpurecool.const import FanMode, FanSpeed, NightMode, Oscillation
from libpurecool.dyson_pure_cool import DysonPureCool, DysonPureCoolLink
from libpurecool.dyson_pure_state import DysonPureCoolState
from libpurecool.dyson_pure_state_v2 import DysonPureCoolV2State
import pytest

from homeassistant.components.dyson import DOMAIN
from homeassistant.components.dyson.fan import (
    ATTR_ANGLE_HIGH,
    ATTR_ANGLE_LOW,
    ATTR_AUTO_MODE,
    ATTR_CARBON_FILTER,
    ATTR_DYSON_SPEED,
    ATTR_DYSON_SPEED_LIST,
    ATTR_FLOW_DIRECTION_FRONT,
    ATTR_HEPA_FILTER,
    ATTR_NIGHT_MODE,
    ATTR_TIMER,
    PRESET_MODE_AUTO,
    SERVICE_SET_ANGLE,
    SERVICE_SET_AUTO_MODE,
    SERVICE_SET_DYSON_SPEED,
    SERVICE_SET_FLOW_DIRECTION_FRONT,
    SERVICE_SET_NIGHT_MODE,
    SERVICE_SET_TIMER,
)
from homeassistant.components.fan import (
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_SPEED,
    ATTR_SPEED_LIST,
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_SPEED,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry

from .common import (
    ENTITY_NAME,
    NAME,
    SERIAL,
    async_get_purecool_device,
    async_get_purecoollink_device,
    async_update_device,
)

ENTITY_ID = f"{PLATFORM_DOMAIN}.{ENTITY_NAME}"


@callback
def async_get_device(spec: Type[DysonPureCoolLink]) -> DysonPureCoolLink:
    """Return a Dyson fan device."""
    if spec == DysonPureCoolLink:
        return async_get_purecoollink_device()
    return async_get_purecool_device()


@pytest.mark.parametrize("device", [DysonPureCoolLink], indirect=True)
async def test_state_purecoollink(
    hass: HomeAssistant, device: DysonPureCoolLink
) -> None:
    """Test the state of a PureCoolLink fan."""
    er = await entity_registry.async_get_registry(hass)
    assert er.async_get(ENTITY_ID).unique_id == SERIAL

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.name == NAME
    attributes = state.attributes
    assert attributes[ATTR_NIGHT_MODE] is True
    assert attributes[ATTR_OSCILLATING] is True
    assert attributes[ATTR_PERCENTAGE] == 10
    assert attributes[ATTR_PRESET_MODE] is None
    assert attributes[ATTR_SPEED] == SPEED_LOW
    assert attributes[ATTR_SPEED_LIST] == [
        SPEED_OFF,
        SPEED_LOW,
        SPEED_MEDIUM,
        SPEED_HIGH,
        PRESET_MODE_AUTO,
    ]
    assert attributes[ATTR_DYSON_SPEED] == 1
    assert attributes[ATTR_DYSON_SPEED_LIST] == list(range(1, 11))
    assert attributes[ATTR_AUTO_MODE] is False
    assert attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_OSCILLATE | SUPPORT_SET_SPEED

    device.state.fan_mode = FanMode.OFF.value
    await async_update_device(hass, device, DysonPureCoolState)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF

    device.state.fan_mode = FanMode.AUTO.value
    device.state.speed = FanSpeed.FAN_SPEED_AUTO.value
    device.state.night_mode = "OFF"
    device.state.oscillation = "OFF"
    await async_update_device(hass, device, DysonPureCoolState)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_NIGHT_MODE] is False
    assert attributes[ATTR_OSCILLATING] is False
    assert attributes[ATTR_PERCENTAGE] is None
    assert attributes[ATTR_PRESET_MODE] == "auto"
    assert attributes[ATTR_SPEED] == PRESET_MODE_AUTO
    assert attributes[ATTR_DYSON_SPEED] == "AUTO"
    assert attributes[ATTR_AUTO_MODE] is True


@pytest.mark.parametrize("device", [DysonPureCool], indirect=True)
async def test_state_purecool(hass: HomeAssistant, device: DysonPureCool) -> None:
    """Test the state of a PureCool fan."""
    er = await entity_registry.async_get_registry(hass)
    assert er.async_get(ENTITY_ID).unique_id == SERIAL

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.name == NAME
    attributes = state.attributes
    assert attributes[ATTR_NIGHT_MODE] is True
    assert attributes[ATTR_OSCILLATING] is True
    assert attributes[ATTR_ANGLE_LOW] == 24
    assert attributes[ATTR_ANGLE_HIGH] == 254
    assert attributes[ATTR_PERCENTAGE] == 10
    assert attributes[ATTR_PRESET_MODE] is None
    assert attributes[ATTR_SPEED] == SPEED_LOW
    assert attributes[ATTR_SPEED_LIST] == [
        SPEED_OFF,
        SPEED_LOW,
        SPEED_MEDIUM,
        SPEED_HIGH,
        PRESET_MODE_AUTO,
    ]
    assert attributes[ATTR_DYSON_SPEED] == 1
    assert attributes[ATTR_DYSON_SPEED_LIST] == list(range(1, 11))
    assert attributes[ATTR_AUTO_MODE] is False
    assert attributes[ATTR_FLOW_DIRECTION_FRONT] is True
    assert attributes[ATTR_TIMER] == "OFF"
    assert attributes[ATTR_HEPA_FILTER] == 100
    assert attributes[ATTR_CARBON_FILTER] == 100
    assert attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_OSCILLATE | SUPPORT_SET_SPEED

    device.state.auto_mode = "ON"
    device.state.night_mode = "OFF"
    device.state.oscillation = "OIOF"
    device.state.speed = "AUTO"
    device.state.front_direction = "OFF"
    device.state.sleep_timer = "0120"
    device.state.carbon_filter_state = "INV"
    await async_update_device(hass, device, DysonPureCoolV2State)
    state = hass.states.get(ENTITY_ID)
    attributes = state.attributes
    assert attributes[ATTR_NIGHT_MODE] is False
    assert attributes[ATTR_OSCILLATING] is False
    assert attributes[ATTR_PERCENTAGE] is None
    assert attributes[ATTR_PRESET_MODE] == "auto"
    assert attributes[ATTR_SPEED] == PRESET_MODE_AUTO
    assert attributes[ATTR_DYSON_SPEED] == "AUTO"
    assert attributes[ATTR_AUTO_MODE] is True
    assert attributes[ATTR_FLOW_DIRECTION_FRONT] is False
    assert attributes[ATTR_TIMER] == "0120"
    assert attributes[ATTR_CARBON_FILTER] == "INV"

    device.state.fan_power = "OFF"
    await async_update_device(hass, device, DysonPureCoolV2State)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "service,service_data,configuration_args",
    [
        (SERVICE_TURN_ON, {}, {"fan_mode": FanMode.FAN}),
        (
            SERVICE_TURN_ON,
            {ATTR_SPEED: SPEED_LOW},
            {"fan_mode": FanMode.FAN, "fan_speed": FanSpeed.FAN_SPEED_4},
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_PERCENTAGE: 40},
            {"fan_mode": FanMode.FAN, "fan_speed": FanSpeed.FAN_SPEED_4},
        ),
        (SERVICE_TURN_OFF, {}, {"fan_mode": FanMode.OFF}),
        (
            SERVICE_OSCILLATE,
            {ATTR_OSCILLATING: True},
            {"oscillation": Oscillation.OSCILLATION_ON},
        ),
        (
            SERVICE_OSCILLATE,
            {ATTR_OSCILLATING: False},
            {"oscillation": Oscillation.OSCILLATION_OFF},
        ),
        (
            SERVICE_SET_SPEED,
            {ATTR_SPEED: SPEED_LOW},
            {"fan_mode": FanMode.FAN, "fan_speed": FanSpeed.FAN_SPEED_4},
        ),
        (
            SERVICE_SET_SPEED,
            {ATTR_SPEED: SPEED_MEDIUM},
            {"fan_mode": FanMode.FAN, "fan_speed": FanSpeed.FAN_SPEED_7},
        ),
        (
            SERVICE_SET_SPEED,
            {ATTR_SPEED: SPEED_HIGH},
            {"fan_mode": FanMode.FAN, "fan_speed": FanSpeed.FAN_SPEED_10},
        ),
    ],
)
@pytest.mark.parametrize("device", [DysonPureCoolLink], indirect=True)
async def test_commands_purecoollink(
    hass: HomeAssistant,
    device: DysonPureCoolLink,
    service: str,
    service_data: dict,
    configuration_args: dict,
) -> None:
    """Test sending commands to a PureCoolLink fan."""
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            **service_data,
        },
        blocking=True,
    )
    device.set_configuration.assert_called_once_with(**configuration_args)


@pytest.mark.parametrize(
    "service,service_data,command,command_args",
    [
        (SERVICE_TURN_ON, {}, "turn_on", []),
        (
            SERVICE_TURN_ON,
            {ATTR_SPEED: SPEED_LOW},
            "set_fan_speed",
            [FanSpeed.FAN_SPEED_4],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_PERCENTAGE: 40},
            "set_fan_speed",
            [FanSpeed.FAN_SPEED_4],
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_PRESET_MODE: "auto"},
            "enable_auto_mode",
            [],
        ),
        (SERVICE_TURN_OFF, {}, "turn_off", []),
        (SERVICE_OSCILLATE, {ATTR_OSCILLATING: True}, "enable_oscillation", []),
        (SERVICE_OSCILLATE, {ATTR_OSCILLATING: False}, "disable_oscillation", []),
        (
            SERVICE_SET_SPEED,
            {ATTR_SPEED: SPEED_LOW},
            "set_fan_speed",
            [FanSpeed.FAN_SPEED_4],
        ),
        (
            SERVICE_SET_SPEED,
            {ATTR_SPEED: SPEED_MEDIUM},
            "set_fan_speed",
            [FanSpeed.FAN_SPEED_7],
        ),
        (
            SERVICE_SET_SPEED,
            {ATTR_SPEED: SPEED_HIGH},
            "set_fan_speed",
            [FanSpeed.FAN_SPEED_10],
        ),
    ],
)
@pytest.mark.parametrize("device", [DysonPureCool], indirect=True)
async def test_commands_purecool(
    hass: HomeAssistant,
    device: DysonPureCool,
    service: str,
    service_data: dict,
    command: str,
    command_args: list,
) -> None:
    """Test sending commands to a PureCool fan."""
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


@pytest.mark.parametrize(
    "service,service_data,configuration_args",
    [
        (
            SERVICE_SET_NIGHT_MODE,
            {ATTR_NIGHT_MODE: True},
            {"night_mode": NightMode.NIGHT_MODE_ON},
        ),
        (
            SERVICE_SET_NIGHT_MODE,
            {ATTR_NIGHT_MODE: False},
            {"night_mode": NightMode.NIGHT_MODE_OFF},
        ),
        (SERVICE_SET_AUTO_MODE, {"auto_mode": True}, {"fan_mode": FanMode.AUTO}),
        (SERVICE_SET_AUTO_MODE, {"auto_mode": False}, {"fan_mode": FanMode.FAN}),
        (
            SERVICE_SET_DYSON_SPEED,
            {ATTR_DYSON_SPEED: "4"},
            {"fan_mode": FanMode.FAN, "fan_speed": FanSpeed.FAN_SPEED_4},
        ),
    ],
)
@pytest.mark.parametrize("device", [DysonPureCoolLink], indirect=True)
async def test_custom_services_purecoollink(
    hass: HomeAssistant,
    device: DysonPureCoolLink,
    service: str,
    service_data: dict,
    configuration_args: dict,
) -> None:
    """Test custom services of a PureCoolLink fan."""
    await hass.services.async_call(
        DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            **service_data,
        },
        blocking=True,
    )
    device.set_configuration.assert_called_once_with(**configuration_args)


@pytest.mark.parametrize(
    "service,service_data,command,command_args",
    [
        (SERVICE_SET_NIGHT_MODE, {ATTR_NIGHT_MODE: True}, "enable_night_mode", []),
        (SERVICE_SET_NIGHT_MODE, {ATTR_NIGHT_MODE: False}, "disable_night_mode", []),
        (SERVICE_SET_AUTO_MODE, {ATTR_AUTO_MODE: True}, "enable_auto_mode", []),
        (SERVICE_SET_AUTO_MODE, {ATTR_AUTO_MODE: False}, "disable_auto_mode", []),
        (SERVICE_SET_AUTO_MODE, {ATTR_AUTO_MODE: False}, "disable_auto_mode", []),
        (
            SERVICE_SET_ANGLE,
            {ATTR_ANGLE_LOW: 10, ATTR_ANGLE_HIGH: 200},
            "enable_oscillation",
            [10, 200],
        ),
        (
            SERVICE_SET_FLOW_DIRECTION_FRONT,
            {ATTR_FLOW_DIRECTION_FRONT: True},
            "enable_frontal_direction",
            [],
        ),
        (
            SERVICE_SET_FLOW_DIRECTION_FRONT,
            {ATTR_FLOW_DIRECTION_FRONT: False},
            "disable_frontal_direction",
            [],
        ),
        (SERVICE_SET_TIMER, {ATTR_TIMER: 0}, "disable_sleep_timer", []),
        (SERVICE_SET_TIMER, {ATTR_TIMER: 10}, "enable_sleep_timer", [10]),
        (
            SERVICE_SET_DYSON_SPEED,
            {ATTR_DYSON_SPEED: "4"},
            "set_fan_speed",
            [FanSpeed("0004")],
        ),
    ],
)
@pytest.mark.parametrize("device", [DysonPureCool], indirect=True)
async def test_custom_services_purecool(
    hass: HomeAssistant,
    device: DysonPureCool,
    service: str,
    service_data: dict,
    command: str,
    command_args: list,
) -> None:
    """Test custom services of a PureCool fan."""
    await hass.services.async_call(
        DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            **service_data,
        },
        blocking=True,
    )
    getattr(device, command).assert_called_once_with(*command_args)


@pytest.mark.parametrize(
    "domain,service,data",
    [
        (PLATFORM_DOMAIN, SERVICE_TURN_ON, {ATTR_SPEED: "AUTO"}),
        (PLATFORM_DOMAIN, SERVICE_SET_SPEED, {ATTR_SPEED: "AUTO"}),
        (DOMAIN, SERVICE_SET_DYSON_SPEED, {ATTR_DYSON_SPEED: "11"}),
    ],
)
@pytest.mark.parametrize("device", [DysonPureCool], indirect=True)
async def test_custom_services_invalid_data(
    hass: HomeAssistant, device: DysonPureCool, domain: str, service: str, data: dict
) -> None:
    """Test custom services calling with invalid data."""
    with pytest.raises(ValueError):
        await hass.services.async_call(
            domain,
            service,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                **data,
            },
            blocking=True,
        )
