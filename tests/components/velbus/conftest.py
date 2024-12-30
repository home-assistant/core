"""Fixtures for the Velbus tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from velbusaio.channels import Button

from homeassistant.components.velbus import VelbusConfigEntry
from homeassistant.components.velbus.const import DOMAIN
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import PORT_TCP

from tests.common import MockConfigEntry


@pytest.fixture(name="controller")
def mock_controller(mock_button: AsyncMock) -> Generator[AsyncMock]:
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
