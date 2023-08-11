"""Test the surepetcare sensor platform."""
from homeassistant.components.surepetcare.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import HOUSEHOLD_ID, MOCK_CONFIG, MOCK_FELAQUA

EXPECTED_ENTITY_IDS = {
    "sensor.pet_flap_battery_level": f"{HOUSEHOLD_ID}-13576-battery",
    "sensor.cat_flap_battery_level": f"{HOUSEHOLD_ID}-13579-battery",
    "sensor.feeder_battery_level": f"{HOUSEHOLD_ID}-12345-battery",
    "sensor.felaqua_battery_level": f"{HOUSEHOLD_ID}-{MOCK_FELAQUA['id']}-battery",
}


async def test_sensors(hass: HomeAssistant, surepetcare) -> None:
    """Test the generation of unique ids."""
    assert await async_setup_component(hass, DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    state_entity_ids = hass.states.async_entity_ids()

    for entity_id, unique_id in EXPECTED_ENTITY_IDS.items():
        assert entity_id in state_entity_ids
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "100"
        entity = entity_registry.async_get(entity_id)
        assert entity.unique_id == unique_id
