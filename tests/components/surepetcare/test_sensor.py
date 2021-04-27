"""Test the surepetcare sensor platform."""
from homeassistant.components.surepetcare.const import DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import HOUSEHOLD_ID, MOCK_CONFIG

EXPECTED_ENTITY_IDS = {
    "sensor.pet_flap_pet_flap_battery_level": f"{HOUSEHOLD_ID}-13576-battery",
    "sensor.cat_flap_cat_flap_battery_level": f"{HOUSEHOLD_ID}-13579-battery",
    "sensor.feeder_feeder_battery_level": f"{HOUSEHOLD_ID}-12345-battery",
}


async def test_binary_sensors(hass, surepetcare) -> None:
    """Test the generation of unique ids."""
    assert await async_setup_component(hass, DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    state_entity_ids = hass.states.async_entity_ids()

    for entity_id, unique_id in EXPECTED_ENTITY_IDS.items():
        assert entity_id in state_entity_ids
        entity = entity_registry.async_get(entity_id)
        assert entity.unique_id == unique_id
