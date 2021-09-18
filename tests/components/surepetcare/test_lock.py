"""The tests for the Sure Petcare lock platform."""

from homeassistant.components.surepetcare.const import DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import HOUSEHOLD_ID, MOCK_CAT_FLAP, MOCK_CONFIG, MOCK_PET_FLAP

EXPECTED_ENTITY_IDS = {
    "lock.locked_in_cat_flap": f"{HOUSEHOLD_ID}-{MOCK_CAT_FLAP['id']}-locked_in",
    "lock.locked_out_cat_flap": f"{HOUSEHOLD_ID}-{MOCK_CAT_FLAP['id']}-locked_out",
    "lock.locked_all_cat_flap": f"{HOUSEHOLD_ID}-{MOCK_CAT_FLAP['id']}-locked_all",
    "lock.locked_in_pet_flap": f"{HOUSEHOLD_ID}-{MOCK_PET_FLAP['id']}-locked_in",
    "lock.locked_out_pet_flap": f"{HOUSEHOLD_ID}-{MOCK_PET_FLAP['id']}-locked_out",
    "lock.locked_all_pet_flap": f"{HOUSEHOLD_ID}-{MOCK_PET_FLAP['id']}-locked_all",
}


async def test_locks(hass, surepetcare) -> None:
    """Test the generation of unique ids."""
    assert await async_setup_component(hass, DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    state_entity_ids = hass.states.async_entity_ids()

    for entity_id, unique_id in EXPECTED_ENTITY_IDS.items():
        assert entity_id in state_entity_ids
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "unlocked"
        entity = entity_registry.async_get(entity_id)
        assert entity.unique_id == unique_id
