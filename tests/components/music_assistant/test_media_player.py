"""Test Music Assistant media player entities."""

from unittest.mock import MagicMock

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_integration_from_fixtures, snapshot_music_assistant_entities


async def test_media_player(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    music_assistant_client: MagicMock,
) -> None:
    """Test media player."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    snapshot_music_assistant_entities(
        hass, entity_registry, snapshot, Platform.MEDIA_PLAYER
    )
