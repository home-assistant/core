"""Test the Sofar Inverter Modbus integration setup and unload."""

from unittest.mock import patch

from modbus_connection.mock import MockModbusConnection

from homeassistant.components.sofar_modbus.const import DOMAIN
from homeassistant.components.sofar_modbus.coordinator import SofarDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import MOCK_USER_INPUT

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a config entry sets up and unloads cleanly, with runtime_data populated."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, SofarDataUpdateCoordinator)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_unrecognized_inverter_raises_not_ready(
    hass: HomeAssistant,
) -> None:
    """Test setup retries when the inverter cannot be identified at all."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="UNRECOGNIZED_SERIAL_XYZ", data=MOCK_USER_INPUT
    )
    entry.add_to_hass(hass)

    unseeded_connection = MockModbusConnection()
    unseeded_connection.for_unit(1)  # zeroed registers -> no recognizable serial

    with patch(
        "homeassistant.components.sofar_modbus.ModbusConnection",
        return_value=unseeded_connection,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_switch_platform_is_forwarded(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the switch platform is set up as part of config entry setup."""
    coordinator: SofarDataUpdateCoordinator = init_integration.runtime_data
    assert "active_power_control" in coordinator.served_components
    assert hass.states.async_entity_ids("switch")
