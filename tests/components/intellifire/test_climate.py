"""Test climate."""

from unittest.mock import patch

from freezegun import freeze_time
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@freeze_time("2021-01-01T12:00:00Z")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry_current: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_fp,
) -> None:
    """Test all entities."""
    with (
        patch("homeassistant.components.intellifire.PLATFORMS", [Platform.CLIMATE]),
    ):
        await setup_integration(hass, mock_config_entry_current)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry_current.entry_id
        )
