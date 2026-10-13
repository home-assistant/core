"""Tests for the aerosmart number platform.

Every number entity is disabled by default (see number.py's module docstring
for why); exercising one means enabling it in the entity registry and
reloading before a state exists to act on.
"""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

KEY = "boost_functions_ventilation_zeitspanne_function_heizung_plus"


async def test_set_native_value_writes_and_refreshes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setting a number's value writes the register and the state reflects it."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.runtime_data.async_wait_initial_refresh()

    unique_id = f"{mock_config_entry.entry_id}_{KEY}"
    entity_id = entity_registry.async_get_entity_id("number", "aerosmart", unique_id)
    assert entity_id is not None

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.runtime_data.async_wait_initial_refresh()

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 90},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "90"
