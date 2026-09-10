"""Test the Flexit climate entity."""

from unittest.mock import MagicMock, patch

from modbus_connection import ModbusError
from modbus_connection.mock import MockModbusUnit
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    HVACAction,
)
from homeassistant.components.flexit.climate import async_setup_platform
from homeassistant.components.flexit.const import DOMAIN
from homeassistant.const import ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.climate.common import async_set_fan_mode, async_set_temperature

CLIMATE_ENTITY_ID = "climate.flexit"

# A plausible, "healthy" set of register values.
DEFAULT_HOLDING: dict[int, int] = {
    8: 215,  # target_temperature -> 21.5
    17: 2,  # fan_mode -> Medium
}
DEFAULT_INPUT: dict[int, int] = {
    9: 200,  # supply_air_temperature -> 20.0
    11: 50,  # outdoor_air_temperature -> 5.0
    8: 120,  # filter_running_hours
    14: 0,  # heat_exchanger_regulation
    15: 0,  # electric_heater_regulation
    13: 0,  # cooling_regulation
    27: 0,  # filter_alarm
    28: 0,  # electric_heater_enabled
    48: 0,  # actual_air_speed
}


@pytest.fixture(autouse=True)
def _load_default_registers(mock_modbus_unit: MockModbusUnit) -> None:
    """Populate the mock unit with a healthy default register set."""
    mock_modbus_unit.holding.update(DEFAULT_HOLDING)
    mock_modbus_unit.input.update(DEFAULT_INPUT)


async def _setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Set up the integration."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_deprecated_yaml_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test deprecated YAML remains functional and creates a repair issue."""
    async_add_entities = MagicMock()
    with patch("homeassistant.components.flexit.climate.get_hub") as get_hub:
        await async_setup_platform(
            hass,
            {"hub": "modbus_hub", "slave": 1, "name": "Flexit"},
            async_add_entities,
        )

    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_no_import")
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.3.0"
    get_hub.assert_called_once_with(hass, "modbus_hub")
    async_add_entities.assert_called_once()


async def test_climate_entity(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entity setup and state."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.flexit._PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device_by_identifier(
        ("flexit", mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device_entry
    assert device_entry.configuration_url is None
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


async def test_climate_entity_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the climate entity reads temperatures and fan mode from registers."""
    await _setup_integration(hass, mock_config_entry)

    state = hass.states.get(CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 21.5
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_FAN_MODE] == "Medium"


@pytest.mark.parametrize(
    ("heating", "cooling", "heat_recovery", "air_speed", "expected_action"),
    [
        (10, 0, 0, 0, HVACAction.HEATING),
        (0, 10, 0, 0, HVACAction.COOLING),
        (0, 0, 10, 0, HVACAction.IDLE),
        (0, 0, 0, 10, HVACAction.FAN),
        (0, 0, 0, 0, HVACAction.OFF),
    ],
)
async def test_climate_entity_hvac_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    heating: int,
    cooling: int,
    heat_recovery: int,
    air_speed: int,
    expected_action: HVACAction,
) -> None:
    """Test hvac_action resolves based on heating/cooling/recovery/air speed."""
    mock_modbus_unit.input[15] = heating
    mock_modbus_unit.input[13] = cooling
    mock_modbus_unit.input[14] = heat_recovery
    mock_modbus_unit.input[48] = air_speed

    await _setup_integration(hass, mock_config_entry)

    assert hass.states.get(CLIMATE_ENTITY_ID).attributes[ATTR_HVAC_ACTION] is (
        expected_action
    )


async def test_climate_entity_set_temperature(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting a valid target temperature writes to the register."""
    await _setup_integration(hass, mock_config_entry)

    await async_set_temperature(hass, temperature=22.5, entity_id=CLIMATE_ENTITY_ID)

    assert hass.states.get(CLIMATE_ENTITY_ID).attributes[ATTR_TEMPERATURE] == 22.5


async def test_climate_entity_set_temperature_handles_modbus_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test setting target temperature handles Modbus write errors."""
    await _setup_integration(hass, mock_config_entry)

    mock_modbus_unit.fail_write(8, ModbusError("write failed"))
    with pytest.raises(HomeAssistantError):
        await async_set_temperature(hass, temperature=22.5, entity_id=CLIMATE_ENTITY_ID)


async def test_climate_entity_set_fan_mode(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting a valid fan mode writes the correct value to the register."""
    await _setup_integration(hass, mock_config_entry)

    await async_set_fan_mode(hass, "High", entity_id=CLIMATE_ENTITY_ID)

    assert hass.states.get(CLIMATE_ENTITY_ID).attributes[ATTR_FAN_MODE] == "High"


async def test_climate_entity_set_fan_mode_handles_modbus_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test setting fan mode handles Modbus write errors."""
    await _setup_integration(hass, mock_config_entry)

    mock_modbus_unit.fail_write(17, ModbusError("write failed"))
    with pytest.raises(HomeAssistantError):
        await async_set_fan_mode(hass, "High", entity_id=CLIMATE_ENTITY_ID)
