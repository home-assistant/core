"""Tests for the Squeezebox alarm switch platform."""

from unittest.mock import MagicMock

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry, snapshot_platform


async def test_entity_registry(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_alarms: MagicMock,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
) -> None:
    """Test squeezebox media_player entity registered in the entity registry."""
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
