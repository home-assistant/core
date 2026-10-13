"""Tests for the aerosmart binary_sensor platform.

Unlike number/switch/select, binary_sensor entities are enabled by default,
so no entity-registry dance is needed to get a state -- but the entity_id is
still looked up via the entity registry by unique_id rather than guessed,
since the object_id is slugified from the translated name in strings.json,
not from the register key.
"""

from modbus_connection.mock import MockModbusUnit

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

# general.relaykontakt_ext_lu, a plain (non-coil) holding register --
# is_on treats any non-zero value as True (see AerosmartBinarySensor).
KEY = "general_relaykontakt_ext_lu"
RELAYKONTAKT_ADDRESS = 252


async def _entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> str:
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.runtime_data.async_wait_initial_refresh()

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
