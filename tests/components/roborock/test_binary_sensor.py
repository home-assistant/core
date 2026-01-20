"""Test Roborock Binary Sensor."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FakeDevice

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.BINARY_SENSOR]


async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensors and check test values are correctly set."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_clean_fluid_empty_with_feature_supported(
    hass: HomeAssistant,
    fake_vacuum: FakeDevice,
    setup_entry: MockConfigEntry,
) -> None:
    """Test that clean_fluid_empty entity appears when feature is supported."""
    # Enable the feature
    fake_vacuum.v1_properties.device_features.is_clean_fluid_delivery_supported = True

    # Reload to pick up changes
    await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_setup(setup_entry.entry_id)
    await hass.async_block_till_done()

    # Verify entity exists
    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, setup_entry.entry_id)
    clean_fluid_entities = [
        e for e in entities if e.unique_id and "clean_fluid_empty" in e.unique_id
    ]
    assert len(clean_fluid_entities) > 0, (
        "clean_fluid_empty entity should be created when feature is supported"
    )
