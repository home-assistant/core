"""Test Google Maps Travel Time initialization."""
from homeassistant.components.google_travel_time import async_migrate_entry
from homeassistant.components.google_travel_time.const import DOMAIN
from homeassistant.helpers.entity_registry import async_get

from tests.common import MockConfigEntry


async def test_migration(hass):
    """Test migration logic from version 1 to 2."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, version=1, entry_id="test", unique_id="test"
    )
    ent_reg = async_get(hass)
    ent_entry = ent_reg.async_get_or_create(
        "sensor", DOMAIN, unique_id="replaceable_unique_id", config_entry=config_entry
    )
    entity_id = ent_entry.entity_id
    config_entry.add_to_hass(hass)
    await async_migrate_entry(hass, config_entry)
    assert config_entry.unique_id is None
    assert ent_reg.async_get(entity_id).unique_id == config_entry.entry_id
