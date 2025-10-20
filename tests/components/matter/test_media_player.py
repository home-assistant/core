"""Test Matter media_player."""

from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import snapshot_matter_entities


@pytest.mark.usefixtures("matter_devices")
async def test_media_players(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the correct entities get created for a media_player device."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.MEDIA_PLAYER)


@pytest.mark.parametrize("node_fixture", ["speaker"])
async def test_media_player(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test media player."""
    state = hass.states.get("media_player.mock_speaker")
    assert state
