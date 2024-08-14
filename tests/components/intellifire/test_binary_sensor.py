"""Test IntelliFire Binary Sensors."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_binary_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry_current: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_fp,
) -> None:
    """Test all entities."""
    with (
        patch(
            "homeassistant.components.intellifire.PLATFORMS", [Platform.BINARY_SENSOR]
        ),
        patch(
            "intellifire4py.unified_fireplace.UnifiedFireplace.build_fireplace_from_common",
            return_value=mock_fp,
        ),
    ):
        await setup_integration(hass, mock_config_entry_current)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry_current.entry_id
        )
