"""Tests for the aerosmart select platform.

The one select entity (``ventilation_betriebsart``, register 5002) is
disabled by default; exercising it means enabling it in the entity registry
and reloading first. Its option labels come from ``VentilationMode`` in
``aerosmart_modbus/enums.py``, verified there against the manufacturer's
Modbus documentation.
"""

from modbus_connection.mock import MockModbusUnit

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

KEY = "ventilation_betriebsart"
BETRIEBSART_ADDRESS = 5002


async def _enabled_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> str:
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.runtime_data.async_wait_initial_refresh()

    unique_id = f"{mock_config_entry.entry_id}_{KEY}"
    entity_id = entity_registry.async_get_entity_id("select", "aerosmart", unique_id)
    assert entity_id is not None

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.runtime_data.async_wait_initial_refresh()
    return entity_id


async def test_options_and_current_option(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
) -> None:
    """Options are the documented labels; current_option decodes the register."""
    mock_modbus_unit_ventilation.holding[BETRIEBSART_ADDRESS] = [0, 4]  # AUTOMATIC

    entity_id = await _enabled_entity_id(hass, entity_registry, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "Automatikbetrieb"
    assert set(state.attributes["options"]) == {
        "Manuell Stufe 0",  # codespell:ignore
        "Manuell Stufe 1",  # codespell:ignore
        "Manuell Stufe 2",  # codespell:ignore
        "Manuell Stufe 3",  # codespell:ignore
        "Automatikbetrieb",
        "Party",
    }


async def test_select_option_writes_the_enum_code(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Selecting a label writes its underlying Modbus code."""
    entity_id = await _enabled_entity_id(hass, entity_registry, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Party"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "Party"
