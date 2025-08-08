"""Test Matter media_player."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import snapshot_matter_entities


@pytest.mark.usefixtures("matter_devices")
async def test_media_player(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the correct entities get created for a media_player device."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.MEDIA_PLAYER)


@pytest.mark.parametrize("node_fixture", ["speaker"])
async def test_media_player_actions(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test media_player entity actions."""
    # Fetch translations
    await async_setup_component(hass, "homeassistant", {})
    entity_id = "media_player.mock_speaker"
    state = hass.states.get(entity_id)
    assert state

    # test mute_volume action (from idle state)
    await hass.services.async_call(
        "media_player",
        "mute_volume",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.OnOff.Commands.Off(),
    )
    matter_client.send_device_command.reset_mock()


@pytest.mark.parametrize("node_fixture", ["speaker"])
async def test_media_player_updates(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test media_player entity updates."""
    entity_id = "media_player.mock_speaker"
    state = hass.states.get(entity_id)
    assert state
    # confirm initial state is idle (as stored in the fixture)
    assert state.state == "off"
