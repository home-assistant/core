"""Test the Dyson 360 eye robot vacuum component."""
from typing import Optional
from unittest.mock import MagicMock

from libpurecool.const import Dyson360EyeMode, PowerMode
from libpurecool.dyson_360_eye import Dyson360Eye

from homeassistant.components.dyson.vacuum import ATTR_POSITION, SUPPORT_DYSON
from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    ATTR_STATUS,
    DOMAIN as VACUUM_DOMAIN,
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

from .common import (
    ENTITY_NAME,
    NAME,
    async_setup_dyson,
    async_update_entity,
    get_device,
)

ENTITY_ID = f"vacuum.{ENTITY_NAME}"


@callback
def _get_vacuum_device() -> Dyson360Eye:
    device = get_device(Dyson360Eye)
    device.state = MagicMock()
    device.state.state = Dyson360EyeMode.FULL_CLEAN_RUNNING
    device.state.battery_level = 85
    device.state.power_mode = PowerMode.QUIET
    device.state.position = (0, 0)
    return device


async def test_state(hass: HomeAssistant) -> None:
    """Test the state of the vacuum."""
    device = await async_setup_dyson(hass, _get_vacuum_device)
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
    state = await async_update_entity(hass, ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_STATUS] == "Stopped - Charging"
    assert state.attributes[ATTR_FAN_SPEED] == "Max"

    device.state.state = Dyson360EyeMode.FULL_CLEAN_PAUSED
    state = await async_update_entity(hass, ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_STATUS] == "Paused"


async def test_commands(hass: HomeAssistant) -> None:
    """Test sending commands to the vacuum."""
    device = await async_setup_dyson(hass, _get_vacuum_device)

    async def _async_call_service(
        service: str,
        attr_name: str,
        device_params: Optional[list] = None,
        state: Optional[str] = None,
        service_data: Optional[dict] = None,
    ) -> None:
        if state is not None:
            device.state.state = state
            await async_update_entity(hass, ENTITY_ID)
        if service_data is None:
            service_data = {}
        await hass.services.async_call(
            VACUUM_DOMAIN,
            service,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                **service_data,
            },
            blocking=True,
        )
        if device_params is None:
            device_params = []
        attr = getattr(device, attr_name)
        attr.assert_called_once_with(*device_params)
        attr.reset_mock()

    await _async_call_service(
        SERVICE_TURN_ON, "start", state=Dyson360EyeMode.INACTIVE_CHARGED
    )
    await _async_call_service(
        SERVICE_TURN_ON, "resume", state=Dyson360EyeMode.FULL_CLEAN_PAUSED
    )
    await _async_call_service(
        SERVICE_TURN_OFF, "pause", state=Dyson360EyeMode.FULL_CLEAN_RUNNING
    )
    await _async_call_service(SERVICE_STOP, "pause")
    await _async_call_service(SERVICE_START_PAUSE, "pause")
    await _async_call_service(
        SERVICE_START_PAUSE, "start", state=Dyson360EyeMode.INACTIVE_CHARGED
    )
    await _async_call_service(
        SERVICE_START_PAUSE, "resume", state=Dyson360EyeMode.FULL_CLEAN_PAUSED
    )
    await _async_call_service(SERVICE_RETURN_TO_BASE, "abort")
    await _async_call_service(
        SERVICE_SET_FAN_SPEED,
        "set_power_mode",
        device_params=[PowerMode.MAX],
        service_data={ATTR_FAN_SPEED: "Max"},
    )
    await _async_call_service(
        SERVICE_SET_FAN_SPEED,
        "set_power_mode",
        device_params=[PowerMode.QUIET],
        service_data={ATTR_FAN_SPEED: "Quiet"},
    )
