"""Tests for the SolarEdge Modbus select entities."""

from unittest.mock import patch

from modbus_connection.mock import MockModbusUnit
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

CONTROL_MODE_ENTITY = "select.solaredge_se10000h_storage_control_mode"
CONTROL_MODE_REGISTER = 57348
EXPORT_MODE_ENTITY = "select.solaredge_se10000h_export_limitation"


async def _setup_select_platform(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with patch(
        "homeassistant.components.solaredge_modbus.PLATFORMS", [Platform.SELECT]
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_selects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """All select entities and their states match the snapshot."""
    await _setup_select_platform(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_limit_type_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """How the site limit is counted is part of the installer's setup."""
    await _setup_select_platform(hass, mock_config_entry)

    entity_id = "select.solaredge_se10000h_export_limit_type"

    assert hass.states.get(entity_id) is None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Selecting an option writes the mode to the device and updates the state."""
    await _setup_select_platform(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: CONTROL_MODE_ENTITY, ATTR_OPTION: "time_of_use"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(CONTROL_MODE_ENTITY)
    assert state is not None
    assert state.state == "time_of_use"
    assert mock_modbus_unit.holding[CONTROL_MODE_REGISTER] == 2


async def test_export_mode_keeps_the_mode_the_inverter_is_set_to(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A mode the inverter is set to is offered even where it does not fit.

    The register is the authority on what the inverter is set to, whatever an
    installer or the SolarEdge app left behind, and an entity may not report a
    state outside its own options.
    """
    # Remove the meter from the register image (no meter model = absent).
    mock_modbus_unit.holding[40188] = 0
    # ...while the inverter is set to a meter-based mode: bit 1 of the mode.
    mock_modbus_unit.holding[57344] = 0b10

    await _setup_select_platform(hass, mock_config_entry)

    state = hass.states.get(EXPORT_MODE_ENTITY)
    assert state is not None
    assert state.state == "export_control_consumption_meter"
    assert state.state in state.attributes[ATTR_OPTIONS]


async def test_export_mode_without_a_meter_hides_the_meter_modes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Limiting export by a meter reading needs a meter to read."""
    # Remove the meter from the register image (no meter model = absent).
    mock_modbus_unit.holding[40188] = 0
    # ...with export limiting switched off, so no mode has to be kept.
    mock_modbus_unit.holding[57344] = 0

    await _setup_select_platform(hass, mock_config_entry)

    state = hass.states.get(EXPORT_MODE_ENTITY)
    assert state is not None
    assert state.state == "disabled"
    assert state.attributes[ATTR_OPTIONS] == ["disabled", "production_control"]


async def test_export_mode_options_with_meter(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A site with a meter offers the meter-based export limitation modes too."""
    await _setup_select_platform(hass, mock_config_entry)

    state = hass.states.get(EXPORT_MODE_ENTITY)
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == [
        "disabled",
        "export_control_export_import_meter",
        "export_control_consumption_meter",
        "production_control",
    ]
