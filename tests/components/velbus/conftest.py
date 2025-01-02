"""Fixtures for the Velbus tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from velbusaio.channels import Button, Relay, SelectedProgram, Temperature

from homeassistant.components.velbus import VelbusConfigEntry
from homeassistant.components.velbus.const import DOMAIN
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import PORT_TCP

from tests.common import MockConfigEntry


@pytest.fixture(name="controller")
def mock_controller(
    mock_button: AsyncMock,
    mock_relay: AsyncMock,
    mock_temperature: AsyncMock,
    mock_select: AsyncMock,
) -> Generator[AsyncMock]:
    """Mock a successful velbus controller."""
    with (
        patch("homeassistant.components.velbus.Velbus", autospec=True) as controller,
        patch(
            "homeassistant.components.velbus.config_flow.velbusaio.controller.Velbus",
            new=controller,
        ),
    ):
        cont = controller.return_value
        cont.get_all_binary_sensor.return_value = [mock_button]
        cont.get_all_button.return_value = [mock_button]
        cont.get_all_switch.return_value = [mock_relay]
        cont.get_all_climate.return_value = [mock_temperature]
        cont.get_all_select.return_value = [mock_select]
        yield controller


@pytest.fixture
def mock_button() -> AsyncMock:
    """Mock a successful velbus channel."""
    channel = AsyncMock(spec=Button)
    channel.get_categories.return_value = ["binary_sensor", "led", "button"]
    channel.get_name.return_value = "ButtonOn"
    channel.get_module_address.return_value = 1
    channel.get_channel_number.return_value = 1
    channel.get_module_type_name.return_value = "VMB4RYLD"
    channel.get_full_name.return_value = "Channel full name"
    channel.get_module_sw_version.return_value = "1.0.0"
    channel.get_module_serial.return_value = "a1b2c3d4e5f6"
    channel.is_closed.return_value = True
    return channel


@pytest.fixture
def mock_temperature() -> AsyncMock:
    """Mock a successful velbus channel."""
    channel = AsyncMock(spec=Temperature)
    channel.get_categories.return_value = ["sensor", "climate"]
    channel.get_name.return_value = "Temperature"
    channel.get_module_address.return_value = 88
    channel.get_channel_number.return_value = 3
    channel.get_module_type_name.return_value = "VMB4GPO"
    channel.get_full_name.return_value = "Channel full name"
    channel.get_module_sw_version.return_value = "3.0.0"
    channel.get_module_serial.return_value = "asdfghjk"
    channel.get_class.return_value = "temperature"
    channel.get_unit.return_value = "°C"
    channel.get_state.return_value = 20.0
    channel.is_temperature.return_value = True
    channel.get_max.return_value = 30.0
    channel.get_min.return_value = 10.0
    channel.get_climate_target.return_value = 21.0
    channel.get_climate_preset.return_value = 1
    channel.get_climate_mode.return_value = "day"
    channel.get_cool_mode.return_value = "heat"
    return channel


@pytest.fixture
def mock_relay() -> AsyncMock:
    """Mock a successful velbus channel."""
    channel = AsyncMock(spec=Relay)
    channel.get_categories.return_value = ["switch"]
    channel.get_name.return_value = "RelayName"
    channel.get_module_address.return_value = 99
    channel.get_channel_number.return_value = 55
    channel.get_module_type_name.return_value = "VMB4RYNO"
    channel.get_full_name.return_value = "Full relay name"
    channel.get_module_sw_version.return_value = "1.0.1"
    channel.get_module_serial.return_value = "qwerty123"
    channel.is_on.return_value = True
    return channel


@pytest.fixture
def mock_select() -> AsyncMock:
    """Mock a successful velbus channel."""
    channel = AsyncMock(spec=SelectedProgram)
    channel.get_categories.return_value = ["select"]
    channel.get_name.return_value = "select"
    channel.get_module_address.return_value = 55
    channel.get_channel_number.return_value = 33
    channel.get_module_type_name.return_value = "VMB4RYNO"
    channel.get_full_name.return_value = "Full module name"
    channel.get_module_sw_version.return_value = "1.1.1"
    channel.get_module_serial.return_value = "qwerty1234567"
    channel.get_options.return_value = ["none", "summer", "winter", "holiday"]
    channel.get_selected_program.return_value = "winter"
    return channel


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
