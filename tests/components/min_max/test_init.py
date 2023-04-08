"""Test the Min/Max integration."""
import pytest

from homeassistant.components.min_max.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("sensor",))
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    platform: str,
) -> None:
    """Test setting up and removing a config entry."""
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")

    input_sensors = ["sensor.input_one", "sensor.input_two"]

    registry = er.async_get(hass)
    group_entity_id = "sensor.sensor_group_my_min_max"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_ids": input_sensors,
            "name": "My min_max",
            "round_digits": 2.0,
            "type": "max",
        },
        title="My min_max",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry imported to Group
    entity = registry.async_get(group_entity_id)
    assert entity is not None
    assert entity.platform == "group"

    # Check the platform is setup correctly
    state = hass.states.get(group_entity_id)
    assert state.state == "20.0"

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry persist when min_max entry is unloaded
    assert hass.states.get(group_entity_id) is not None
    assert registry.async_get(group_entity_id) is not None
