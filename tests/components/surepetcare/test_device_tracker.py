"""The tests for the Sure Petcare device tracker platform."""

from homeassistant.components.device_tracker import ATTR_SOURCE_TYPE, SourceType
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import HOUSEHOLD_ID

from tests.common import MockConfigEntry

EXPECTED_ENTITY_IDS = {
    "device_tracker.pet": f"{HOUSEHOLD_ID}-24680-tracker",
    "device_tracker.pet_outdoor": f"{HOUSEHOLD_ID}-24681-tracker",
    "device_tracker.pet_unknown": f"{HOUSEHOLD_ID}-24682-tracker",
}


async def test_device_tracker(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test the creation of device tracker entities."""
    state_entity_ids = hass.states.async_entity_ids()

    # Expected states for each pet based on their "where" value
    expected_states = {
        "device_tracker.pet": STATE_HOME,  # where: 1 (inside)
        "device_tracker.pet_outdoor": STATE_NOT_HOME,  # where: 2 (outside)
        "device_tracker.pet_unknown": "unknown",  # where: -1 (unknown)
    }

    # Expected extra state attributes for each pet
    expected_attributes = {
        "device_tracker.pet": {"since": "2020-08-23T23:10:50"},
        "device_tracker.pet_outdoor": {"since": "2020-08-23T23:15:30"},
        "device_tracker.pet_unknown": {"since": "2020-08-23T23:20:45"},
    }

    for entity_id, unique_id in EXPECTED_ENTITY_IDS.items():
        assert entity_id in state_entity_ids
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_states[entity_id]
        assert state.attributes[ATTR_SOURCE_TYPE] == SourceType.GPS

        # Check extra state attributes
        expected_attrs = expected_attributes[entity_id]
        assert state.attributes["since"] == expected_attrs["since"]

        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        assert entity.unique_id == unique_id
