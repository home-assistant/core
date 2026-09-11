"""Tests for the SolarEdge Modbus number entities."""

from unittest.mock import patch

from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

BACKUP_RESERVE_ENTITY = "number.solaredge_se10000h_backup_reserve"
BACKUP_RESERVE_REGISTER = 57352


async def _setup_number_platform(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with patch(
        "homeassistant.components.solaredge_modbus.PLATFORMS", [Platform.NUMBER]
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_numbers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """All number entities and their states match the snapshot."""
    await _setup_number_platform(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_power_factor_setpoint_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reactive power is grid-code territory and stays out of the way."""
    await _setup_number_platform(hass, mock_config_entry)

    entity_id = "number.solaredge_se10000h_power_factor_setpoint"

    assert hass.states.get(entity_id) is None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Setting a number writes to the device and updates the state."""
    await _setup_number_platform(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: BACKUP_RESERVE_ENTITY, ATTR_VALUE: 25},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(BACKUP_RESERVE_ENTITY)
    assert state is not None
    assert state.state == "25.0"


async def test_set_value_communication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A write that fails on the wire raises a translated error."""
    await _setup_number_platform(hass, mock_config_entry)

    mock_modbus_unit.fail_write(BACKUP_RESERVE_REGISTER, ModbusTimeoutError("timeout"))

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: BACKUP_RESERVE_ENTITY, ATTR_VALUE: 25},
            blocking=True,
        )

    assert excinfo.value.translation_key == "communication_error"


async def test_set_value_rejected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A value the device rejects raises a translated error."""
    await _setup_number_platform(hass, mock_config_entry)

    mock_modbus_unit.fail_write(BACKUP_RESERVE_REGISTER, ValueError("does not fit"))

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: BACKUP_RESERVE_ENTITY, ATTR_VALUE: 25},
            blocking=True,
        )

    assert excinfo.value.translation_key == "rejected_value"
