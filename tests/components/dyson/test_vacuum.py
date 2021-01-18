"""Test the Dyson 360 eye robot vacuum component."""
from unittest.mock import MagicMock

from libpurecool.const import Dyson360EyeMode, PowerMode
from libpurecool.dyson_360_eye import Dyson360Eye
import pytest

from homeassistant.components.dyson.vacuum import ATTR_POSITION, SUPPORT_DYSON
from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    ATTR_STATUS,
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START_PAUSE,
    SERVICE_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry

from .common import ENTITY_NAME, NAME, SERIAL, async_update_device, get_basic_device

ENTITY_ID = f"{PLATFORM_DOMAIN}.{ENTITY_NAME}"


@callback
def get_device() -> Dyson360Eye:
    """Return a Dyson 360 Eye device."""
    device = get_basic_device(Dyson360Eye)
    device.state = MagicMock()
    device.state.state = Dyson360EyeMode.FULL_CLEAN_RUNNING
    device.state.battery_level = 85
    device.state.power_mode = PowerMode.QUIET
    device.state.position = (0, 0)
    return device


async def test_state(hass: HomeAssistant, device: Dyson360Eye) -> None:
    """Test the state of the vacuum."""
    er = await entity_registry.async_get_registry(hass)
    assert er.async_get(ENTITY_ID).unique_id == SERIAL

    state = hass.states.get(ENTITY_ID)
    assert state.name == NAME
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_STATUS] == "Cleaning"
    assert attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_DYSON
    assert attributes[ATTR_BATTERY_LEVEL] == 85
    assert attributes[ATTR_POSITION] == "(0, 0)"
    assert attributes[ATTR_FAN_SPEED] == "Quiet"
    assert attributes[ATTR_FAN_SPEED_LIST] == ["Quiet", "Max"]

    device.state.state = Dyson360EyeMode.INACTIVE_CHARGING
    device.state.power_mode = PowerMode.MAX
    await async_update_device(hass, device)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_STATUS] == "Stopped - Charging"
    assert state.attributes[ATTR_FAN_SPEED] == "Max"

    device.state.state = Dyson360EyeMode.FULL_CLEAN_PAUSED
    await async_update_device(hass, device)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_STATUS] == "Paused"


@pytest.mark.parametrize(
    "service,command,state",
    [
        (SERVICE_TURN_ON, "start", Dyson360EyeMode.INACTIVE_CHARGED),
        (SERVICE_TURN_ON, "resume", Dyson360EyeMode.FULL_CLEAN_PAUSED),
        (SERVICE_TURN_OFF, "pause", Dyson360EyeMode.FULL_CLEAN_RUNNING),
        (SERVICE_STOP, "pause", Dyson360EyeMode.FULL_CLEAN_RUNNING),
        (SERVICE_START_PAUSE, "pause", Dyson360EyeMode.FULL_CLEAN_RUNNING),
        (SERVICE_START_PAUSE, "pause", Dyson360EyeMode.FULL_CLEAN_RUNNING),
        (SERVICE_START_PAUSE, "start", Dyson360EyeMode.INACTIVE_CHARGED),
        (SERVICE_START_PAUSE, "resume", Dyson360EyeMode.FULL_CLEAN_PAUSED),
        (SERVICE_RETURN_TO_BASE, "abort", Dyson360EyeMode.FULL_CLEAN_PAUSED),
    ],
)
async def test_commands(
    hass: HomeAssistant, device: Dyson360Eye, service: str, command: str, state: str
) -> None:
    """Test sending commands to the vacuum."""
    device.state.state = state
    await async_update_device(hass, device)
    await hass.services.async_call(
        PLATFORM_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    getattr(device, command).assert_called_once_with()


async def test_set_fan_speed(hass: HomeAssistant, device: Dyson360Eye):
    """Test setting fan speed of the vacuum."""
    fan_speed_map = {
        "Max": PowerMode.MAX,
        "Quiet": PowerMode.QUIET,
    }
    for service_speed, command_speed in fan_speed_map.items():
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_SET_FAN_SPEED,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_SPEED: service_speed},
            blocking=True,
        )
        device.set_power_mode.assert_called_with(command_speed)
