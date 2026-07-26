"""Tests for the Fumis binary sensor entities."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import UNIQUE_ID

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.parametrize(
    "init_integration", [Platform.BINARY_SENSOR], indirect=True
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Fumis binary sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("device_fixture", ["info_minimal"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_binary_sensors_conditional_creation(
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test door binary sensor is not created when data is missing."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    unique_ids = {entry.unique_id for entry in entity_entries}

    assert f"{UNIQUE_ID}_door" not in unique_ids
