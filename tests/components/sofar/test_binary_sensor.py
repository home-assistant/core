"""Test the Sofar Inverter Modbus binary sensor platform."""

from unittest.mock import patch

from modbus_connection.mock import MockModbusConnection
import pytest
from sofar_modbus.modern.faults import FaultCategory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sofar.binary_sensor import FAULT_SENSOR_DESCRIPTIONS
from homeassistant.components.sofar.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_MODEL, MOCK_SERIAL, MOCK_USER_INPUT, seed_pv_inverter

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities match their snapshot on a PV device."""
    connection = MockModbusConnection()
    seed_pv_inverter(connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT, title=MOCK_MODEL
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.sofar.PLATFORMS", [Platform.BINARY_SENSOR]),
        patch(
            "homeassistant.components.sofar.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: connection.for_unit(
                unit_id
            ),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_no_faults_reports_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test every category is off when nothing is seeded."""
    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{MOCK_SERIAL}_fault_grid"
    )
    assert entity_id is not None
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_one_bit_only_lights_its_own_category(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a fan failure isn't masked by a shutdown bit in the same register."""
    unit = mock_connection.for_unit(1)
    unit.holding[0x0405] = 0b1  # ID001_GRID_OVER_VOLTAGE
    unit.holding[0x040F] = 0b100000001  # ID161_FORCED_SHUTDOWN | ID169_FAN_1_FAILURE
    unit.holding[0x0410] = 0b100  # ID179_BMS_HIGH_TEMPERATURE_PROTECTION

    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    on_categories = {"grid", "shutdown", "fan", "battery"}
    for description in FAULT_SENSOR_DESCRIPTIONS:
        entity_id = entity_registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN, DOMAIN, f"{MOCK_SERIAL}_{description.key}"
        )
        assert entity_id is not None
        assert (state := hass.states.get(entity_id)) is not None
        expected = (
            STATE_ON if description.category.value in on_categories else STATE_OFF
        )
        assert state.state == expected, description.category


async def test_enabled_by_default_excludes_commercial_hardware(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test combiner box, string fuse, input fuse and AFCI start disabled."""
    entries = [
        e
        for e in er.async_entries_for_config_entry(
            entity_registry, init_integration.entry_id
        )
        if e.domain == BINARY_SENSOR_DOMAIN
    ]
    assert len(entries) == len(FAULT_SENSOR_DESCRIPTIONS)

    disabled_categories = {
        FaultCategory(e.unique_id.removeprefix(f"{MOCK_SERIAL}_fault_"))
        for e in entries
        if e.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    }
    assert disabled_categories == {
        FaultCategory.ARC_FAULT,
        FaultCategory.COMBINER_BOX,
        FaultCategory.INPUT_FUSE,
        FaultCategory.STRING_FUSE,
    }
