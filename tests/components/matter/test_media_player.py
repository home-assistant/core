"""Test Matter media_player."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_VOLUME_MUTE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
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


@pytest.mark.parametrize("node_fixture", ["speaker"])
async def test_volume_mute_on(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    node_fixture: str,
) -> None:
    """Test muting the media player."""
    entity_id = "media_player.mock_speaker"
    state = hass.states.get(entity_id)
    assert state is not None

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_VOLUME_MUTED: True,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.OnOff.Commands.Off(),
    )


@pytest.mark.parametrize("node_fixture", ["speaker"])
async def test_media_player_actions(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    node_fixture: str,
) -> None:
    """Test media_player entity actions."""
    entity_id = "media_player.mock_speaker"
    state = hass.states.get(entity_id)
    assert state

    # test mute_volume action (from idle state)
    await hass.services.async_call(
        "media_player",
        "volume_mute",
        {
            "entity_id": entity_id,
            "is_volume_muted": True,
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

    # test volume_set action
    await hass.services.async_call(
        "media_player",
        "volume_set",
        {
            "entity_id": entity_id,
            "volume_level": 0.5,  # 50% volume
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 2
    # First command unmutes
    assert matter_client.send_device_command.call_args_list[0] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.OnOff.Commands.On(),
    )
    # Second command sets volume
    assert matter_client.send_device_command.call_args_list[1] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.LevelControl.Commands.MoveToLevel(level=127),  # 50%
    )
    matter_client.send_device_command.reset_mock()
