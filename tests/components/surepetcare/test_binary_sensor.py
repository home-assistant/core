"""The tests for the Sure Petcare binary sensor platform."""
from homeassistant.components.surepetcare.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import HOUSEHOLD_ID, HUB_ID, MOCK_CONFIG

EXPECTED_ENTITY_IDS = {
    "binary_sensor.pet_flap_connectivity": f"{HOUSEHOLD_ID}-13576-connectivity",
    "binary_sensor.cat_flap_connectivity": f"{HOUSEHOLD_ID}-13579-connectivity",
    "binary_sensor.feeder_connectivity": f"{HOUSEHOLD_ID}-12345-connectivity",
    "binary_sensor.pet": f"{HOUSEHOLD_ID}-24680",
    "binary_sensor.hub": f"{HOUSEHOLD_ID}-{HUB_ID}",
}


async def test_binary_sensors(hass: HomeAssistant, surepetcare) -> None:
    """Test the generation of unique ids."""
    assert await async_setup_component(hass, DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    state_entity_ids = hass.states.async_entity_ids()

    for entity_id, unique_id in EXPECTED_ENTITY_IDS.items():
        assert entity_id in state_entity_ids
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"
        entity = entity_registry.async_get(entity_id)
        assert entity.unique_id == unique_id
