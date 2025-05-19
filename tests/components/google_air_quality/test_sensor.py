"""Test the Google Air Quality media source."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test of the sensors."""
    with patch(
        "homeassistant.components.google_air_quality.PLATFORMS",
        [Platform.SENSOR],
    ):
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
