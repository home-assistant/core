"""Test the surepetcare sensor platform."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

from . import HOUSEHOLD_ID, MOCK_FELAQUA, MOCK_PET

from tests.common import MockConfigEntry

EXPECTED_ENTITY_IDS = {
    "sensor.pet_flap_battery_level": f"{HOUSEHOLD_ID}-13576-battery",
    "sensor.cat_flap_battery_level": f"{HOUSEHOLD_ID}-13579-battery",
    "sensor.feeder_battery_level": f"{HOUSEHOLD_ID}-12345-battery",
    "sensor.felaqua_battery_level": f"{HOUSEHOLD_ID}-{MOCK_FELAQUA['id']}-battery",
    "sensor.pet_last_seen_flap_device_id": f"{HOUSEHOLD_ID}-24680-last-seen-flap-device",
    "sensor.pet_last_seen_user_id": f"{HOUSEHOLD_ID}-24680-last-seen-user",
}

DEFAULT_DISABLED_ENTITIES = [
    "sensor.pet_last_seen_flap_device_id",
    "sensor.pet_last_seen_user_id",
]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test the generation of unique ids and sensor states."""
    state_entity_ids = hass.states.async_entity_ids()

    for entity_id, unique_id in EXPECTED_ENTITY_IDS.items():
        assert entity_id in state_entity_ids
        state = hass.states.get(entity_id)
        assert state
        if entity_id == "sensor.pet_last_seen_flap_device_id":
            assert state.state == str(MOCK_PET["position"]["device_id"])
        elif entity_id == "sensor.pet_last_seen_user_id":
            assert state.state == str(MOCK_PET["position"]["user_id"])
        elif entity_id.endswith("_battery_level"):
            assert state.state == "100"
        entity = entity_registry.async_get(entity_id)
        assert entity.unique_id == unique_id


async def test_default_disabled_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test sensor entities that are disabled by default."""
    for entity_id in DEFAULT_DISABLED_ENTITIES:
        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.disabled_by == RegistryEntryDisabler.INTEGRATION
        assert not hass.states.get(entity_id)
