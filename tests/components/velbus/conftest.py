"""Fixtures for the Velbus tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from velbusaio.channels import (
    Blind,
    Button,
    ButtonCounter,
    Dimmer,
    LightSensor,
    Relay,
    SelectedProgram,
    SensorNumber,
    Temperature,
)
from velbusaio.module import Module

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
    mock_buttoncounter: AsyncMock,
    mock_sensornumber: AsyncMock,
    mock_lightsensor: AsyncMock,
    mock_dimmer: AsyncMock,
    mock_module_no_subdevices: AsyncMock,
    mock_module_subdevices: AsyncMock,
    mock_cover: AsyncMock,
    mock_cover_no_position: AsyncMock,
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
        cont.get_all_sensor.return_value = [
            mock_buttoncounter,
            mock_temperature,
            mock_sensornumber,
            mock_lightsensor,
        ]
        cont.get_all_light.return_value = [mock_dimmer]
        cont.get_all_led.return_value = [mock_button]
        cont.get_all_cover.return_value = [mock_cover, mock_cover_no_position]
        cont.get_modules.return_value = {
            1: mock_module_no_subdevices,
            2: mock_module_no_subdevices,
            3: mock_module_no_subdevices,
            4: mock_module_no_subdevices,
            99: mock_module_subdevices,
        }
        cont.get_module.return_value = mock_module_subdevices
        yield controller


@pytest.fixture
def mock_module_no_subdevices(
    mock_relay: AsyncMock,
) -> AsyncMock:
    """Mock a velbus module."""
    module = AsyncMock(spec=Module)
    module.get_type_name.return_value = "VMB4RYLD"
    module.get_addresses.return_value = [1, 2, 3, 4]
    module.get_name.return_value = "BedRoom"
    module.get_sw_version.return_value = "1.0.0"
    module.is_loaded.return_value = True
    module.get_channels.return_value = {}
    return module


@pytest.fixture
def mock_module_subdevices() -> AsyncMock:
    """Mock a velbus module."""
    module = AsyncMock(spec=Module)
    module.get_type_name.return_value = "VMB2BLE"
    module.get_addresses.return_value = [88]
    module.get_name.return_value = "Kitchen"
    module.get_sw_version.return_value = "2.0.0"
    module.is_loaded.return_value = True
    module.get_channels.return_value = {}
    return module


@pytest.fixture
def mock_button() -> AsyncMock:
    """Mock a successful velbus channel."""
    channel = AsyncMock(spec=Button)
    channel.get_categories.return_value = ["binary_sensor", "led", "button"]
    channel.get_name.return_value = "ButtonOn"
    channel.get_module_address.return_value = 1
    channel.get_channel_number.return_value = 1
    channel.get_module_type_name.return_value = "VMB4RYLD"
    channel.get_module_type.return_value = 99
    channel.get_full_name.return_value = "Bedroom kid 1"
    channel.get_module_sw_version.return_value = "1.0.0"
    channel.get_module_serial.return_value = "a1b2c3d4e5f6"
    channel.is_sub_device.return_value = False
    channel.is_closed.return_value = True
    channel.is_on.return_value = False
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
    channel.get_full_name.return_value = "Living room"
    channel.get_module_sw_version.return_value = "3.0.0"
    channel.get_module_serial.return_value = "asdfghjk"
    channel.get_module_type.return_value = 1
    channel.is_sub_device.return_value = False
    channel.is_counter_channel.return_value = False
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
    channel.get_module_address.return_value = 88
    channel.get_channel_number.return_value = 55
    channel.get_module_type_name.return_value = "VMB4RYNO"
    channel.get_full_name.return_value = "Living room"
    channel.get_module_sw_version.return_value = "1.0.1"
    channel.get_module_serial.return_value = "qwerty123"
    channel.get_module_type.return_value = 2
    channel.is_sub_device.return_value = True
    channel.is_on.return_value = True
    return channel


@pytest.fixture
def mock_select() -> AsyncMock:
    """Mock a successful velbus channel."""
    channel = AsyncMock(spec=SelectedProgram)
    channel.get_categories.return_value = ["select"]
    channel.get_name.return_value = "select"
    channel.get_module_address.return_value = 88
    channel.get_channel_number.return_value = 33
    channel.get_module_type_name.return_value = "VMB4RYNO"
    channel.get_module_type.return_value = 3
    channel.get_full_name.return_value = "Kitchen"
    channel.get_module_sw_version.return_value = "1.1.1"
    channel.get_module_serial.return_value = "qwerty1234567"
    channel.is_sub_device.return_value = False
    channel.get_options.return_value = ["none", "summer", "winter", "holiday"]
    channel.get_selected_program.return_value = "winter"
    return channel


@pytest.fixture
def mock_buttoncounter() -> AsyncMock:
    """Mock a successful velbus channel."""
    channel = AsyncMock(spec=ButtonCounter)
    channel.get_categories.return_value = ["sensor"]
    channel.get_name.return_value = "ButtonCounter"
    channel.get_module_address.return_value = 88
    channel.get_channel_number.return_value = 2
    channel.get_module_type_name.return_value = "VMB7IN"
    channel.get_module_type.return_value = 4
    channel.get_full_name.return_value = "Input"
    channel.get_module_sw_version.return_value = "1.0.0"
    channel.get_module_serial.return_value = "a1b2c3d4e5f6"
    channel.is_sub_device.return_value = True
    channel.is_counter_channel.return_value = True
    channel.is_temperature.return_value = False
    channel.get_state.return_value = 100
    channel.get_unit.return_value = "W"
    channel.get_counter_state.return_value = 100
    channel.get_counter_unit.return_value = "kWh"
    return channel


@pytest.fixture
def mock_sensornumber() -> AsyncMock:
    """Mock a successful velbus channel."""
    channel = AsyncMock(spec=SensorNumber)
    channel.get_categories.return_value = ["sensor"]
    channel.get_name.return_value = "SensorNumber"
    channel.get_module_address.return_value = 2
    channel.get_channel_number.return_value = 3
    channel.get_module_type_name.return_value = "VMB7IN"
    channel.get_module_type.return_value = 8
    channel.get_full_name.return_value = "Input"
    channel.get_module_sw_version.return_value = "1.0.0"
    channel.get_module_serial.return_value = "a1b2c3d4e5f6"
    channel.is_sub_device.return_value = False
    channel.is_counter_channel.return_value = False
    channel.is_temperature.return_value = False
    channel.get_unit.return_value = "m"
    channel.get_state.return_value = 10
    return channel


@pytest.fixture
def mock_lightsensor() -> AsyncMock:
    """Mock a successful velbus channel."""
    channel = AsyncMock(spec=LightSensor)
    channel.get_categories.return_value = ["sensor"]
    channel.get_name.return_value = "LightSensor"
    channel.get_module_address.return_value = 2
    channel.get_channel_number.return_value = 4
    channel.get_module_type_name.return_value = "VMB7IN"
    channel.get_module_type.return_value = 8
    channel.get_full_name.return_value = "Input"
    channel.get_module_sw_version.return_value = "1.0.0"
    channel.get_module_serial.return_value = "a1b2c3d4e5f6"
    channel.is_sub_device.return_value = False
    channel.is_counter_channel.return_value = False
    channel.is_temperature.return_value = False
    channel.get_unit.return_value = "illuminance"
    channel.get_state.return_value = 250
    return channel


@pytest.fixture
def mock_dimmer() -> AsyncMock:
    """Mock a successful velbus channel."""
    channel = AsyncMock(spec=Dimmer)
    channel.get_categories.return_value = ["light"]
    channel.get_name.return_value = "Dimmer"
    channel.get_module_address.return_value = 88
    channel.get_channel_number.return_value = 10
    channel.get_module_type_name.return_value = "VMBDN1"
    channel.get_module_type.return_value = 9
    channel.get_full_name.return_value = "Dimmer full name"
    channel.get_module_sw_version.return_value = "1.0.0"
    channel.get_module_serial.return_value = "a1b2c3d4e5f6g7"
    channel.is_sub_device.return_value = True
    channel.is_on.return_value = False
    channel.get_dimmer_state.return_value = 33
    return channel


@pytest.fixture
def mock_cover() -> AsyncMock:
    """Mock a successful velbus channel."""
    channel = AsyncMock(spec=Blind)
    channel.get_categories.return_value = ["cover"]
    channel.get_name.return_value = "CoverName"
    channel.get_module_address.return_value = 88
    channel.get_channel_number.return_value = 9
    channel.get_module_type_name.return_value = "VMB2BLE"
    channel.get_module_type.return_value = 10
    channel.get_full_name.return_value = "Basement"
    channel.get_module_sw_version.return_value = "1.0.1"
    channel.get_module_serial.return_value = "1234"
    channel.is_sub_device.return_value = True
    channel.support_position.return_value = True
    channel.get_position.return_value = 50
    channel.is_closed.return_value = False
    channel.is_open.return_value = True
    channel.is_opening.return_value = False
    channel.is_closing.return_value = False
    return channel


@pytest.fixture
def mock_cover_no_position() -> AsyncMock:
    """Mock a successful velbus channel."""
    channel = AsyncMock(spec=Blind)
    channel.get_categories.return_value = ["cover"]
    channel.get_name.return_value = "CoverNameNoPos"
    channel.get_module_address.return_value = 88
    channel.get_channel_number.return_value = 11
    channel.get_module_type_name.return_value = "VMB2BLE"
    channel.get_module_type.return_value = 10
    channel.get_full_name.return_value = "Basement"
    channel.get_module_sw_version.return_value = "1.0.1"
    channel.get_module_serial.return_value = "12345"
    channel.is_sub_device.return_value = True
    channel.support_position.return_value = False
    channel.get_position.return_value = None
    channel.is_closed.return_value = False
    channel.is_open.return_value = True
    channel.is_opening.return_value = True
    channel.is_closing.return_value = True
    return channel


@pytest.fixture(name="config_entry")
async def mock_config_entry(
    hass: HomeAssistant,
    controller: AsyncMock,
) -> VelbusConfigEntry:
    """Create and register mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: PORT_TCP, CONF_NAME: "velbus home"},
    )
    config_entry.add_to_hass(hass)
    return config_entry
