"""Fixtures for the Velbus tests."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.velbus import VelbusConfigEntry
from homeassistant.components.velbus.const import DOMAIN
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import PORT_TCP

from tests.common import MockConfigEntry

ButtonOn = {
    "get_categories.return_value": ["binary_sensor"],
    "get_name.return_value": "ButtonOn",
    "get_module_address.return_value": 1,
    "get_channel_number.return_value": 1,
    "get_module_type_name.return_value": "VMB4RYLD",
    "get_full_name.return_value": "Channel full name",
    "get_module_sw_version.return_value": "1.0.0",
    "get_module_serial.return_value": "a1b2c3d4e5f6",
    "is_on.return_value": True,
}


@pytest.fixture(name="controller")
def mock_full_controller() -> MagicMock:
    """Mock a successful velbus controller."""
    with patch("homeassistant.components.velbus.Velbus", autospec=True) as controller:
        controller.get_all_binary_sensor.return_value = [
            mock_channel("Button", ButtonOn),
        ]
        yield controller


def mock_channel(channel_type: str, channel_data: dict) -> MagicMock:
    """Mock a successful velbus channel."""
    with patch(f"velbusaio.channels.{channel_type}") as channel:
        channel.configure_mock(**channel_data)
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


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    config_entry: VelbusConfigEntry,
) -> None:
    """Load the Velbus integration."""
    hass.config.components.add(DOMAIN)

    assert await async_setup_component(hass, DOMAIN, {}) is True
    await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(config_entry.entry_id) is True
    await hass.async_block_till_done()
