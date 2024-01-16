"""The tests for the Sure Petcare lock platform."""
import pytest
from surepy.exceptions import SurePetcareError

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import HOUSEHOLD_ID, MOCK_CAT_FLAP, MOCK_PET_FLAP

from tests.common import MockConfigEntry

EXPECTED_ENTITY_IDS = {
    "lock.cat_flap_locked_in": f"{HOUSEHOLD_ID}-{MOCK_CAT_FLAP['id']}-locked_in",
    "lock.cat_flap_locked_out": f"{HOUSEHOLD_ID}-{MOCK_CAT_FLAP['id']}-locked_out",
    "lock.cat_flap_locked_all": f"{HOUSEHOLD_ID}-{MOCK_CAT_FLAP['id']}-locked_all",
    "lock.pet_flap_locked_in": f"{HOUSEHOLD_ID}-{MOCK_PET_FLAP['id']}-locked_in",
    "lock.pet_flap_locked_out": f"{HOUSEHOLD_ID}-{MOCK_PET_FLAP['id']}-locked_out",
    "lock.pet_flap_locked_all": f"{HOUSEHOLD_ID}-{MOCK_PET_FLAP['id']}-locked_all",
}


async def test_locks(
    hass: HomeAssistant, surepetcare, mock_config_entry_setup: MockConfigEntry
) -> None:
    """Test the generation of unique ids."""
    entity_registry = er.async_get(hass)
    state_entity_ids = hass.states.async_entity_ids()

    for entity_id, unique_id in EXPECTED_ENTITY_IDS.items():
        surepetcare.reset_mock()

        assert entity_id in state_entity_ids
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "unlocked"
        entity = entity_registry.async_get(entity_id)
        assert entity.unique_id == unique_id

        await hass.services.async_call(
            "lock", "unlock", {"entity_id": entity_id}, blocking=True
        )
        state = hass.states.get(entity_id)
        assert state.state == "unlocked"
        # already unlocked
        assert surepetcare.unlock.call_count == 0

        await hass.services.async_call(
            "lock", "lock", {"entity_id": entity_id}, blocking=True
        )
        state = hass.states.get(entity_id)
        assert state.state == "locked"
        if "locked_in" in entity_id:
            assert surepetcare.lock_in.call_count == 1
        elif "locked_out" in entity_id:
            assert surepetcare.lock_out.call_count == 1
        elif "locked_all" in entity_id:
            assert surepetcare.lock.call_count == 1

        # lock again should not trigger another request
        await hass.services.async_call(
            "lock", "lock", {"entity_id": entity_id}, blocking=True
        )
        state = hass.states.get(entity_id)
        assert state.state == "locked"
        if "locked_in" in entity_id:
            assert surepetcare.lock_in.call_count == 1
        elif "locked_out" in entity_id:
            assert surepetcare.lock_out.call_count == 1
        elif "locked_all" in entity_id:
            assert surepetcare.lock.call_count == 1

        await hass.services.async_call(
            "lock", "unlock", {"entity_id": entity_id}, blocking=True
        )
        state = hass.states.get(entity_id)
        assert state.state == "unlocked"
        assert surepetcare.unlock.call_count == 1


async def test_lock_failing(
    hass: HomeAssistant, surepetcare, mock_config_entry_setup: MockConfigEntry
) -> None:
    """Test handling of lock failing."""
    surepetcare.lock_in.side_effect = SurePetcareError
    surepetcare.lock_out.side_effect = SurePetcareError
    surepetcare.lock.side_effect = SurePetcareError

    for entity_id in EXPECTED_ENTITY_IDS:
        with pytest.raises(SurePetcareError):
            await hass.services.async_call(
                "lock", "lock", {"entity_id": entity_id}, blocking=True
            )
        state = hass.states.get(entity_id)
        assert state.state == "unlocked"


async def test_unlock_failing(
    hass: HomeAssistant, surepetcare, mock_config_entry_setup: MockConfigEntry
) -> None:
    """Test handling of unlock failing."""
    entity_id = list(EXPECTED_ENTITY_IDS)[0]

    await hass.services.async_call(
        "lock", "lock", {"entity_id": entity_id}, blocking=True
    )
    surepetcare.unlock.side_effect = SurePetcareError

    with pytest.raises(SurePetcareError):
        await hass.services.async_call(
            "lock", "unlock", {"entity_id": entity_id}, blocking=True
        )
    state = hass.states.get(entity_id)
    assert state.state == "locked"
