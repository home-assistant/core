"""Test IntelliClima Binary Sensors."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry_current: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test all entities."""

    with (
        patch(
            "homeassistant.components.intelliclima.PLATFORMS", [Platform.BINARY_SENSOR]
        ),
    ):
        await setup_integration(hass, mock_config_entry_current)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry_current.entry_id
        )
