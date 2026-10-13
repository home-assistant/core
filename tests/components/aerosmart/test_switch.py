"""Tests for the aerosmart switch platform.

Every switch entity is disabled by default (see switch.py's module
docstring); exercising one means enabling it in the entity registry and
reloading before a state exists to act on.
"""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

KEY = "boost_functions_ventilation_function_heizung_plus"


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
    entity_id = entity_registry.async_get_entity_id("switch", "aerosmart", unique_id)
    assert entity_id is not None

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.runtime_data.async_wait_initial_refresh()
    return entity_id


async def test_turn_on_writes_and_refreshes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Turning on writes 1 to the register and the state follows."""
    entity_id = await _enabled_entity_id(hass, entity_registry, mock_config_entry)

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "on"


async def test_turn_off_writes_and_refreshes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Turning off writes 0 to the register and the state follows."""
    entity_id = await _enabled_entity_id(hass, entity_registry, mock_config_entry)

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "off"
