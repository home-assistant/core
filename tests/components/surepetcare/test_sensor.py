"""Test the surepetcare sensor platform."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import HOUSEHOLD_ID, MOCK_FELAQUA

from tests.common import MockConfigEntry

EXPECTED_ENTITY_IDS = {
    "sensor.pet_flap_battery_level": f"{HOUSEHOLD_ID}-13576-battery",
    "sensor.cat_flap_battery_level": f"{HOUSEHOLD_ID}-13579-battery",
    "sensor.feeder_battery_level": f"{HOUSEHOLD_ID}-12345-battery",
    "sensor.felaqua_battery_level": f"{HOUSEHOLD_ID}-{MOCK_FELAQUA['id']}-battery",
}


async def test_sensors(
    hass: HomeAssistant, surepetcare, mock_config_entry_setup: MockConfigEntry
) -> None:
    """Test the generation of unique ids."""
    entity_registry = er.async_get(hass)
    state_entity_ids = hass.states.async_entity_ids()

    for entity_id, unique_id in EXPECTED_ENTITY_IDS.items():
        assert entity_id in state_entity_ids
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "100"
        entity = entity_registry.async_get(entity_id)
        assert entity.unique_id == unique_id
