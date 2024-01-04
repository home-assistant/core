"""Tests for glances sensors."""
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.glances.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_USER_INPUT

from tests.common import MockConfigEntry


async def test_sensor_states(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Test sensor states are correctly collected from library."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


@pytest.mark.parametrize(
    ("object_id", "old_unique_id", "new_unique_id"),
    [
        (
            "glances_ssl_used_percent",
            "0.0.0.0-Glances /ssl used percent",
            "/ssl-disk_use_percent",
        ),
        (
            "glances_cpu_thermal_1_temperature",
            "0.0.0.0-Glances cpu_thermal 1 Temperature",
            "cpu_thermal 1-temperature_core",
        ),
    ],
)
async def test_migrate_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    object_id: str,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Test unique id migration."""
    old_config_data = {**MOCK_USER_INPUT, "name": "Glances"}
    entry = MockConfigEntry(domain=DOMAIN, data=old_config_data)
    entry.add_to_hass(hass)

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        suggested_object_id=object_id,
        disabled_by=None,
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == f"{entry.entry_id}-{new_unique_id}"
