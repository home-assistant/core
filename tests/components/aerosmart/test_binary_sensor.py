"""Tests for the aerosmart binary sensor platform."""

from unittest.mock import patch

from modbus_connection.mock import MockModbusUnit
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aerosmart.binary_sensor import BINARY_SENSOR_DESCRIPTIONS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

KEY = "general_relaykontakt_ext_lu"
RELAYKONTAKT_ADDRESS = 252


async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all binary sensor entities."""
    with patch(
        "homeassistant.components.aerosmart.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def _entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> str:
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    unique_id = f"{mock_config_entry.entry_id}_{KEY}"
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", "aerosmart", unique_id
    )
    assert entity_id is not None
    return entity_id


async def test_is_on_true_for_nonzero_register(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
) -> None:
    """A non-zero register value reads as on."""
    mock_modbus_unit_ventilation.holding[RELAYKONTAKT_ADDRESS] = [0, 1]

    entity_id = await _entity_id(hass, entity_registry, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


async def test_is_on_false_for_zero_register(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
) -> None:
    """A zero register value reads as off."""
    mock_modbus_unit_ventilation.holding[RELAYKONTAKT_ADDRESS] = [0, 0]

    entity_id = await _entity_id(hass, entity_registry, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


async def test_diagnostic_entity_is_enabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Diagnostic binary sensors are available for automations by default."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unique_id = (
        f"{mock_config_entry.entry_id}_outside_temperature_aussenluftfuehler_vorhanden"
    )
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", "aerosmart", unique_id
    )
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is None
    assert hass.states.get(entity_id) is not None


async def test_descriptions_are_backed_by_boolean_metadata(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Every exposed binary sensor is typed as boolean by the library."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = mock_config_entry.runtime_data.device
    for description in BINARY_SENSOR_DESCRIPTIONS:
        subsystem = getattr(device, description.component)
        metadata = subsystem.require_metadata_for(description.attribute)
        assert metadata.value_kind == "boolean"
        assert metadata.writable is False
