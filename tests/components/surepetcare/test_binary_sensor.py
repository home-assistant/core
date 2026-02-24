"""The tests for the Sure Petcare binary sensor platform."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import HOUSEHOLD_ID, HUB_ID

from tests.common import MockConfigEntry

EXPECTED_ENTITY_IDS = {
    "binary_sensor.pet_flap_connectivity": f"{HOUSEHOLD_ID}-13576-connectivity",
    "binary_sensor.cat_flap_connectivity": f"{HOUSEHOLD_ID}-13579-connectivity",
    "binary_sensor.feeder_connectivity": f"{HOUSEHOLD_ID}-12345-connectivity",
    "binary_sensor.pet": f"{HOUSEHOLD_ID}-24680",
    "binary_sensor.hub": f"{HOUSEHOLD_ID}-{HUB_ID}",
    "binary_sensor.pet_flap_curfew_enabled": f"{HOUSEHOLD_ID}-13576-curfew-enabled",
    "binary_sensor.cat_flap_curfew_enabled": f"{HOUSEHOLD_ID}-13579-curfew-enabled",
    "binary_sensor.pet_flap_no_curfew_curfew_enabled": f"{HOUSEHOLD_ID}-18976-curfew-enabled",
}


async def test_binary_sensors(
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
        if "no_curfew" in entity_id:
            # The pet flap without curfew should have curfew disabled
            assert state.state == "off"
        else:
            assert state.state == "on"
        entity = entity_registry.async_get(entity_id)
        assert entity.unique_id == unique_id


async def test_curfew_enabled_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test curfew enabled binary sensors."""
    # Test cat flap curfew enabled sensor
    cat_flap_curfew = hass.states.get("binary_sensor.cat_flap_curfew_enabled")
    assert cat_flap_curfew is not None
    assert cat_flap_curfew.state == "on"

    # Test pet flap curfew enabled sensor
    pet_flap_curfew = hass.states.get("binary_sensor.pet_flap_curfew_enabled")
    assert pet_flap_curfew is not None
    assert pet_flap_curfew.state == "on"

    # Test pet flap without curfew sensor is disabled
    pet_flap_no_curfew = hass.states.get(
        "binary_sensor.pet_flap_no_curfew_curfew_enabled"
    )
    assert pet_flap_no_curfew is not None
    assert pet_flap_no_curfew.state == "off"
