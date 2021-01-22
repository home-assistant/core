"""Common utils for Dyson tests."""

from typing import Optional, Type
from unittest import mock
from unittest.mock import MagicMock

from libpurecool.const import SLEEP_TIMER_OFF, Dyson360EyeMode, FanMode, PowerMode
from libpurecool.dyson_360_eye import Dyson360Eye
from libpurecool.dyson_device import DysonDevice
from libpurecool.dyson_pure_cool import DysonPureCool, FanSpeed
from libpurecool.dyson_pure_cool_link import DysonPureCoolLink

from homeassistant.components.dyson import CONF_LANGUAGE, DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback

SERIAL = "XX-XXXXX-XX"
NAME = "Temp Name"
ENTITY_NAME = "temp_name"
IP_ADDRESS = "0.0.0.0"

BASE_PATH = "homeassistant.components.dyson"

CONFIG = {
    DOMAIN: {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "password",
        CONF_LANGUAGE: "US",
        CONF_DEVICES: [
            {
                "device_id": SERIAL,
                "device_ip": IP_ADDRESS,
            }
        ],
    }
}


def load_mock_device(device: DysonDevice) -> None:
    """Load the mock with default values so it doesn't throw errors."""
    device.serial = SERIAL
    device.name = NAME
    device.connect = mock.Mock(return_value=True)
    device.auto_connect = mock.Mock(return_value=True)
    device.state.hepa_filter_state = 0
    device.state.carbon_filter_state = 0
    device.state.speed = FanSpeed.FAN_SPEED_1.value
    device.state.oscillation_angle_low = "000"
    device.state.oscillation_angle_high = "000"
    device.state.filter_life = "000"
    device.state.heat_target = 200
    if hasattr(device, "environmental_state"):
        device.environmental_state.particulate_matter_25 = "0000"
        device.environmental_state.particulate_matter_10 = "0000"
        device.environmental_state.nitrogen_dioxide = "0000"
        device.environmental_state.volatil_organic_compounds = "0000"
        device.environmental_state.volatile_organic_compounds = "0000"
        device.environmental_state.temperature = 250


def get_basic_device(spec: Type[DysonDevice]) -> DysonDevice:
    """Return a basic device with common fields filled out."""
    device = MagicMock(spec=spec)
    load_mock_device(device)
    return device


@callback
def async_get_360eye_device(state=Dyson360EyeMode.FULL_CLEAN_RUNNING) -> Dyson360Eye:
    """Return a Dyson 360 Eye device."""
    device = get_basic_device(Dyson360Eye)
    device.state.state = state
    device.state.battery_level = 85
    device.state.power_mode = PowerMode.QUIET
    device.state.position = (0, 0)
    return device


@callback
def async_get_purecoollink_device() -> DysonPureCoolLink:
    """Return a Dyson Pure Cool Link device."""
    device = get_basic_device(DysonPureCoolLink)
    device.state.fan_mode = FanMode.FAN.value
    device.state.speed = FanSpeed.FAN_SPEED_1.value
    device.state.night_mode = "ON"
    device.state.oscillation = "ON"
    return device


@callback
def async_get_purecool_device() -> DysonPureCool:
    """Return a Dyson Pure Cool device."""
    device = get_basic_device(DysonPureCool)
    device.state.fan_power = "ON"
    device.state.speed = FanSpeed.FAN_SPEED_1.value
    device.state.night_mode = "ON"
    device.state.oscillation = "OION"
    device.state.oscillation_angle_low = "0024"
    device.state.oscillation_angle_high = "0254"
    device.state.auto_mode = "OFF"
    device.state.front_direction = "ON"
    device.state.sleep_timer = SLEEP_TIMER_OFF
    device.state.hepa_filter_state = "0100"
    device.state.carbon_filter_state = "0100"
    return device


async def async_update_device(
    hass: HomeAssistant, device: DysonDevice, state_type: Optional[Type] = None
) -> None:
    """Update the device using callback function."""
    callbacks = [args[0][0] for args in device.add_message_listener.call_args_list]
    message = MagicMock(spec=state_type)

    # Combining sync calls to avoid multiple executors
    def _run_callbacks():
        for callback_fn in callbacks:
            callback_fn(message)

    await hass.async_add_executor_job(_run_callbacks)
    await hass.async_block_till_done()
