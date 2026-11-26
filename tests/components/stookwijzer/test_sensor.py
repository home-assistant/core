"""Tests for the Stookwijzer sensor platform."""

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the sensor platform."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Stookwijzer entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
