"""Common utils for Dyson tests."""

from typing import Callable, Optional, Type
from unittest import mock
from unittest.mock import MagicMock, patch

from libpurecool.dyson_device import DysonDevice
from libpurecool.dyson_pure_cool import FanSpeed

from homeassistant.components.dyson import CONF_LANGUAGE, DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, State

from tests.common import async_setup_component

SERIAL = "XX-XXXXX-XX"
NAME = "Temp Name"
ENTITY_NAME = "temp_name"

BASE_PATH = "homeassistant.components.dyson"


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


def get_device(spec: Type[DysonDevice]) -> DysonDevice:
    """Return a mocked device."""
    device = MagicMock(spec=spec)
    load_mock_device(device)
    return device


async def async_setup_dyson(
    hass: HomeAssistant, get_device: Callable[[], DysonDevice]
) -> DysonDevice:
    """Set up the Dyson integration."""
    device = get_device()
    with patch(f"{BASE_PATH}.DysonAccount.login", return_value=True), patch(
        f"{BASE_PATH}.DysonAccount.devices", return_value=[device]
    ):
        await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_USERNAME: "user@example.com",
                    CONF_PASSWORD: "password",
                    CONF_LANGUAGE: "US",
                    CONF_DEVICES: [
                        {
                            "device_id": SERIAL,
                            "device_ip": "0.0.0.0",
                        }
                    ],
                }
            },
        )
        await hass.async_block_till_done()

    return device


async def async_update_device(
    hass: HomeAssistant, device: DysonDevice, state_type: Optional[Type]
) -> State:
    """Update the device using callback function."""
    callback = device.add_message_listener.call_args[0][0]
    message = MagicMock(spec=state_type)
    callback(message)
    await hass.async_block_till_done()
