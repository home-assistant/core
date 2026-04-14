"""Test the Min/Max integration."""

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.min_max.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_migrates_to_groups(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting up and removing a config entry."""
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")

    input_sensors = ["sensor.input_one", "sensor.input_two"]

    min_max_entity_id = "sensor.my_min_max"

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
    await hass.async_block_till_done(wait_background_tasks=True)

    # Check the entity is registered in the entity registry
    entity = entity_registry.async_get(min_max_entity_id)
    assert entity is not None
    assert entity.config_entry_id is not None
    assert entity.config_entry_id != config_entry.entry_id
    assert entity.platform == "group"

    # Check the platform is setup correctly
    state = hass.states.get(min_max_entity_id)
    assert state.state == "20.0"

    config_entry = hass.config_entries.async_entries("group")[0]
    assert config_entry.as_dict() == snapshot(
        exclude=props("created_at", "entry_id", "modified_at")
    )
    config_entry_min_max = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry_min_max

    freezer.tick(60 * 5)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    config_entry_min_max = hass.config_entries.async_entries(DOMAIN)
    assert not config_entry_min_max
