"""Tests for the Jewish Calendar component's init."""

import pytest

from homeassistant.components.jewish_calendar.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("old_key", "new_key"),
    [
        ("first_light", "alot_hashachar"),
        ("sunset", "shkia"),
        ("havdalah", "havdalah"),  # Test no change
    ],
)
async def test_migrate_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    old_key: str,
    new_key: str,
) -> None:
    """Test unique id migration."""
    config_entry.add_to_hass(hass)

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=f"{config_entry.entry_id}-{old_key}",
        config_entry=config_entry,
    )
    assert entity.unique_id.endswith(f"-{old_key}")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == f"{config_entry.entry_id}-{new_key}"
