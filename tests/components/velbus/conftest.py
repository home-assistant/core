"""Fixtures for the Velbus tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from velbusaio.channels import Button

from homeassistant.components.velbus import VelbusConfigEntry
from homeassistant.components.velbus.const import DOMAIN
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import PORT_TCP

from tests.common import MockConfigEntry

ButtonOn = {
    "get_categories.return_value": ["binary_sensor", "led", "button"],
    "get_name.return_value": "ButtonOn",
    "get_module_address.return_value": 1,
    "get_channel_number.return_value": 1,
    "get_module_type_name.return_value": "VMB4RYLD",
    "get_full_name.return_value": "Channel full name",
    "get_module_sw_version.return_value": "1.0.0",
    "get_module_serial.return_value": "a1b2c3d4e5f6",
    "is_closed.return_value": False,
    "is_on.return_value": True,
    # TODO set_led_state
    # TODO press
}

BlindUp = {
    "get_categories.return_value": ["cover"],
    "get_name.return_value": "BlindUp",
    "get_module_address.return_value": 2,
    "get_channel_number.return_value": 3,
    "get_module_type_name.return_value": "VMB2BL",
    "get_full_name.return_value": "Blind name",
    "get_module_sw_version.return_value": "1.2.0",
    "get_module_serial.return_value": "a2b3c4d5e6f7",
    "get_position.return_value": 50,
    "get_state.return_value": "up",
    "is_opening.return_value": False,
    "is_closing.return_value": False,
    "is_stopped.return_value": False,
    "is_closed.return_value": True,
    "is_open.return_value": False,
    "support_position.return_value": True,
    # TODO open
    # TODO close
    # TODO stop
    # TODO set_position
}


@pytest.fixture(name="controller")
def mock_controller(mock_buttonOn: AsyncMock) -> MagicMock:
    """Mock a successful velbus controller."""
    with (
        patch("homeassistant.components.velbus.Velbus", autospec=True) as controller,
        patch(
            "homeassistant.components.velbus.config_flow.velbusaio.controller.Velbus",
            new=controller,
        ),
    ):
        controller.get_all_binary_sensor.return_value = [mock_buttonOn]
        print(controller.get_all_binary_sensor())
        yield controller


@pytest.fixture
def mock_buttonOn() -> AsyncMock:
    """Mock a successful velbus channel."""
    channel = AsyncMock(spec=Button)
    channel.configure_mock(**ButtonOn)
    return channel


# moddify this one to set the runtime_data correctly
@pytest.fixture(name="config_entry")
async def mock_config_entry(
    hass: HomeAssistant,
    controller: MagicMock,
) -> VelbusConfigEntry:
    """Create and register mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: PORT_TCP, CONF_NAME: "velbus home"},
    )
    config_entry.add_to_hass(hass)
    return config_entry
