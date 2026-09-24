"""Tests for the Ouman EH-800 sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import SCENARIOS

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("scenario", SCENARIOS.keys(), indirect=True)
@pytest.mark.parametrize("init_integration", [Platform.SENSOR], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities for each registry-set scenario."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
