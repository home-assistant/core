"""Test the surepetcare sensor platform."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import HOUSEHOLD_ID, MOCK_FELAQUA, MOCK_PET

from tests.common import MockConfigEntry, async_fire_time_changed

EXPECTED_ENTITY_IDS = {
    "sensor.pet_flap_battery_level": f"{HOUSEHOLD_ID}-13576-battery",
    "sensor.cat_flap_battery_level": f"{HOUSEHOLD_ID}-13579-battery",
    "sensor.feeder_battery_level": f"{HOUSEHOLD_ID}-12345-battery",
    "sensor.felaqua_battery_level": f"{HOUSEHOLD_ID}-{MOCK_FELAQUA['id']}-battery",
}

DISABLED_ENTITY_IDS = {
    "sensor.pet_last_seen_flap_device_id": f"{HOUSEHOLD_ID}-24680-last-seen-flap-device",
    "sensor.pet_last_seen_user_id": f"{HOUSEHOLD_ID}-24680-last-seen-user",
}


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test the generation of unique ids."""
    state_entity_ids = hass.states.async_entity_ids()

    for entity_id, unique_id in EXPECTED_ENTITY_IDS.items():
        assert entity_id in state_entity_ids
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "100"
        entity = entity_registry.async_get(entity_id)
        assert entity.unique_id == unique_id


async def test_disabled_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test disabled sensor entities."""
    flap_device_id_entity = "sensor.pet_last_seen_flap_device_id"
    user_id_entity = "sensor.pet_last_seen_user_id"

    assert not hass.states.get(flap_device_id_entity)
    assert not hass.states.get(user_id_entity)

    with patch("homeassistant.config_entries.RELOAD_AFTER_UPDATE_DELAY", 1):
        entity_registry.async_update_entity(
            entity_id=flap_device_id_entity, disabled_by=None
        )
        entity_registry.async_update_entity(entity_id=user_id_entity, disabled_by=None)
        await hass.async_block_till_done(wait_background_tasks=True)

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(flap_device_id_entity)
    assert state
    assert state.state == str(MOCK_PET["position"]["device_id"])
    entity = entity_registry.async_get(flap_device_id_entity)
    assert entity.unique_id == DISABLED_ENTITY_IDS[flap_device_id_entity]

    state = hass.states.get(user_id_entity)
    assert state
    assert state.state == str(MOCK_PET["position"]["user_id"])
    entity = entity_registry.async_get(user_id_entity)
    assert entity.unique_id == DISABLED_ENTITY_IDS[user_id_entity]
