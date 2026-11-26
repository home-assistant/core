"""Tests for the Intesis Modbus integration setup."""

from unittest.mock import MagicMock

from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.intesis_modbus.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The entry loads, registers the gateway and its unit, and unloads cleanly."""
    assert init_integration.state is ConfigEntryState.LOADED
    entry_id = init_integration.entry_id
    gateway = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry_id), entry_id
    )
    assert gateway is not None
    assert gateway.manufacturer == "Intesis (HMS Networks)"
    assert gateway.model == "INMBSMHI001R000"
    assert gateway.name == "INMBSMHI001R000"
    assert gateway.sw_version == "20"
    unit = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_unit"), entry_id
    )
    assert unit is not None
    assert unit.manufacturer == "Mitsubishi Heavy Industries"
    assert unit.name == "INMBSMHI001R000 air conditioner"
    assert unit.via_device_id == gateway.id
    assert dr.async_entries_for_config_entry(device_registry, entry_id) == [
        gateway,
        unit,
    ]
    await hass.config_entries.async_unload(entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("registers", [{11: 65535}])
async def test_setup_with_unreachable_unit(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A gateway that cannot reach its unit still loads, the unit unavailable."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert (
        len(
            dr.async_entries_for_config_entry(
                device_registry, init_integration.entry_id
            )
        )
        == 2
    )
    state = hass.states.get("climate.inmbsmhi001r000_air_conditioner")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_setup_retries_when_silent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """A gateway that does not answer puts the entry in setup retry."""
    mock_connection.for_unit(1).fail_requests(ModbusTimeoutError())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_wrong_model_is_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """A gateway of another brand than the entry says is a setup error."""
    mock_connection.for_unit(1).holding[49] = 0x0801
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
