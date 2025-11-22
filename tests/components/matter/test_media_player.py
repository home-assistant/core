"""Test Matter media_player."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from chip.clusters.Objects import LevelControl
from matter_server.client.models.node import MatterNode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)

endpoint_id = 1


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
        endpoint_id=endpoint_id,
        command=clusters.OnOff.Commands.Off(),
    )
    matter_client.send_device_command.reset_mock()

    # test volume_set action
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_VOLUME_LEVEL: 0.5,  # 50% volume
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 2
    # First command unmutes
    assert matter_client.send_device_command.call_args_list[0] == call(
        node_id=matter_node.node_id,
        endpoint_id=endpoint_id,
        command=clusters.OnOff.Commands.On(),
    )
    # Second command sets volume
    assert matter_client.send_device_command.call_args_list[1] == call(
        node_id=matter_node.node_id,
        endpoint_id=endpoint_id,
        command=clusters.LevelControl.Commands.MoveToLevel(level=127),  # 50%
    )
    matter_client.send_device_command.reset_mock()


@pytest.mark.parametrize("node_fixture", ["speaker"])
async def test_volume_mute_off(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    node_fixture: str,
) -> None:
    """Test unmuting the media player."""
    entity_id = "media_player.mock_speaker"
    state = hass.states.get(entity_id)
    assert state is not None

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_VOLUME_MUTED: False,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=endpoint_id,
        command=clusters.OnOff.Commands.On(),
    )


@pytest.mark.parametrize("node_fixture", ["speaker"])
async def test_volume_set_zero(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    node_fixture: str,
) -> None:
    """Test setting volume to 0 sends only Off (mute) command."""
    entity_id = "media_player.mock_speaker"
    state = hass.states.get(entity_id)
    assert state is not None

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_VOLUME_LEVEL: 0.0,
        },
        blocking=True,
    )

    # Should only send the Off command (mute) and return early
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.OnOff.Commands.Off(),
    )


@pytest.mark.parametrize("node_fixture", ["speaker"])
async def test_volume_level_none(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test handling of None volume level."""
    entity_id = "media_player.mock_speaker"

    # Get initial state
    state = hass.states.get(entity_id)
    assert state is not None
    initial_volume = state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL)
    initial_muted = state.attributes.get(ATTR_MEDIA_VOLUME_MUTED)

    # Set CurrentLevel attribute to None to simulate unavailable attribute
    # LevelControl cluster ID: 8, CurrentLevel attribute ID: 0
    set_node_attribute(
        matter_node,
        endpoint_id,
        LevelControl.id,
        0,  # CurrentLevel attribute id
        None,
    )
    await trigger_subscription_callback(hass, matter_client)

    # Verify state remains unchanged when volume is None
    state = hass.states.get(entity_id)
    assert state is not None
    # Volume and mute state should not have been updated
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == initial_volume
    assert state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) == initial_muted


@pytest.mark.parametrize("node_fixture", ["speaker"])
async def test_volume_current_level_zero(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that CurrentLevel == 0 sets muted state to True."""
    entity_id = "media_player.mock_speaker"

    # Ensure we start from a non-zero level to see the transition
    set_node_attribute(matter_node, 1, LevelControl.id, 0, 100)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is False

    # Set CurrentLevel to 0 (Matter spec: 0 represents off for LevelControl)
    set_node_attribute(matter_node, 1, LevelControl.id, 0, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state is not None
    # Entity should report muted when level is 0
    assert state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is True
