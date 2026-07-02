"""Tests for the Geniushub water heater platform."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_geniushub_cloud")
async def test_cloud_all_water_heaters(
    hass: HomeAssistant,
    mock_cloud_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation of the Genius Hub water heater entities."""
    with patch("homeassistant.components.geniushub.PLATFORMS", [Platform.WATER_HEATER]):
        await setup_integration(hass, mock_cloud_config_entry)

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_cloud_config_entry.entry_id
    )
