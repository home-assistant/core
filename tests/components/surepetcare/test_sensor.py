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
    "sensor.pet_flap_curfew_lock_time": f"{HOUSEHOLD_ID}-13576-curfew-lock-time",
    "sensor.pet_flap_curfew_unlock_time": f"{HOUSEHOLD_ID}-13576-curfew-unlock-time",
    "sensor.cat_flap_curfew_lock_time": f"{HOUSEHOLD_ID}-13579-curfew-lock-time",
    "sensor.cat_flap_curfew_unlock_time": f"{HOUSEHOLD_ID}-13579-curfew-unlock-time",
    "sensor.pet_flap_no_curfew_curfew_lock_time": f"{HOUSEHOLD_ID}-18976-curfew-lock-time",
    "sensor.pet_flap_no_curfew_curfew_unlock_time": f"{HOUSEHOLD_ID}-18976-curfew-unlock-time",
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
        entity = entity_registry.async_get(entity_id)
        assert entity.unique_id == unique_id

    # Test battery sensors have correct state
    assert hass.states.get("sensor.pet_flap_battery_level").state == "100"
    assert hass.states.get("sensor.cat_flap_battery_level").state == "100"
    assert hass.states.get("sensor.feeder_battery_level").state == "100"

    # Test curfew time sensors have correct states
    assert hass.states.get("sensor.pet_flap_curfew_lock_time").state == "20:00"
    assert hass.states.get("sensor.pet_flap_curfew_unlock_time").state == "08:00"
    assert hass.states.get("sensor.cat_flap_curfew_lock_time").state == "22:00"
    assert hass.states.get("sensor.cat_flap_curfew_unlock_time").state == "07:00"


async def test_curfew_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test curfew time sensors."""
    # Verify pet flap has correct curfew times
    pet_flap_lock = hass.states.get("sensor.pet_flap_curfew_lock_time")
    assert pet_flap_lock is not None
    assert pet_flap_lock.state == "20:00"

    pet_flap_unlock = hass.states.get("sensor.pet_flap_curfew_unlock_time")
    assert pet_flap_unlock is not None
    assert pet_flap_unlock.state == "08:00"

    # Verify cat flap has correct curfew times
    cat_flap_lock = hass.states.get("sensor.cat_flap_curfew_lock_time")
    assert cat_flap_lock is not None
    assert cat_flap_lock.state == "22:00"

    cat_flap_unlock = hass.states.get("sensor.cat_flap_curfew_unlock_time")
    assert cat_flap_unlock is not None
    assert cat_flap_unlock.state == "07:00"

    # Verify pet flap without curfew has correct states
    pet_flap_no_curfew_lock = hass.states.get(
        "sensor.pet_flap_no_curfew_curfew_lock_time"
    )
    assert pet_flap_no_curfew_lock is not None
    assert pet_flap_no_curfew_lock.state == "unknown"
