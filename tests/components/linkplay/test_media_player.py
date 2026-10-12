"""Tests for the LinkPlay media player."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

from linkplay.bridge import (
    LinkPlayBridge,
    LinkPlayDevice,
    LinkPlayMultiroom,
    LinkPlayPlayer,
)
from linkplay.consts import API_ENDPOINT, LoopMode, PlayingStatus
import pytest

from homeassistant.components.linkplay.const import DOMAIN, SHARED_DATA
from homeassistant.components.media_player import (
    ATTR_GROUP_MEMBERS,
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_JOIN,
    RepeatMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_STATE_CHANGED,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import setup_integration
from .conftest import HOST, mock_lp_aiohttp_client

from tests.common import MockConfigEntry, async_capture_events, async_load_fixture

ENTITY_ID = "media_player.smart_zone_1_54b9"
LEADER_ENTITY_ID = "media_player.leader"
LEADER_UUID = "FF31F09E-5001-FBDE-0546-2DBFFF31F0AA"
RENAMED_ENTITY_ID = "media_player.renamed"


@pytest.fixture
async def leader_player(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> AsyncGenerator[AsyncMock]:
    """Set up a device that is a follower in a multiroom group and mock its leader."""

    with (
        mock_lp_aiohttp_client() as mock_session,
        patch.object(LinkPlayMultiroom, "update_status", return_value=None),
    ):
        for endpoint in (f"https://{HOST}", f"http://{HOST}"):
            mock_session.get(
                API_ENDPOINT.format(endpoint, "getPlayerStatusEx"),
                text=await async_load_fixture(
                    hass, "getPlayerEx_follower.json", DOMAIN
                ),
            )
            mock_session.get(
                API_ENDPOINT.format(endpoint, "getStatusEx"),
                text=await async_load_fixture(hass, "getStatusEx.json", DOMAIN),
            )

        await setup_integration(hass, mock_config_entry)

        player = AsyncMock(spec=LinkPlayPlayer)
        player.status = PlayingStatus.PLAYING
        player.title = "Zelda's Lullaby"
        player.artist = "Spiritual Concepts"
        player.album = "Cello Covers"
        player.current_position_in_seconds = 17
        player.total_length = 62000
        player.total_length_in_seconds = 62
        player.loop_mode = LoopMode.RANDOM_PLAYBACK

        leader = AsyncMock(spec=LinkPlayBridge)
        leader.player = player
        leader.device = AsyncMock(spec=LinkPlayDevice)
        leader.device.uuid = LEADER_UUID
        hass.data[DOMAIN][SHARED_DATA].entity_to_bridge[LEADER_ENTITY_ID] = LEADER_UUID

        bridge = mock_config_entry.runtime_data.bridge
        bridge.multiroom = LinkPlayMultiroom(leader)
        bridge.multiroom.followers = [bridge]

        await async_update_entity(hass, ENTITY_ID)
        yield player


@pytest.mark.usefixtures("leader_player")
async def test_follower_mirrors_leader_media_info(hass: HomeAssistant) -> None:
    """Test that a follower shows the media info of its group leader."""

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_PLAYING
    assert state.attributes[ATTR_MEDIA_TITLE] == "Zelda's Lullaby"
    assert state.attributes[ATTR_MEDIA_ARTIST] == "Spiritual Concepts"
    assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == "Cello Covers"
    assert state.attributes[ATTR_MEDIA_POSITION] == 17
    assert state.attributes[ATTR_MEDIA_DURATION] == 62
    assert state.attributes[ATTR_MEDIA_REPEAT] == RepeatMode.ALL
    assert state.attributes[ATTR_MEDIA_SHUFFLE] is True

    # volume and source stay on the follower itself
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.8
    assert state.attributes[ATTR_INPUT_SOURCE] == "Follower"


@pytest.mark.parametrize(
    ("service", "service_data", "method", "method_args"),
    [
        pytest.param(SERVICE_MEDIA_PAUSE, {}, "pause", (), id="pause"),
        pytest.param(SERVICE_MEDIA_PLAY, {}, "resume", (), id="play"),
        pytest.param(SERVICE_MEDIA_STOP, {}, "stop", (), id="stop"),
        pytest.param(SERVICE_MEDIA_NEXT_TRACK, {}, "next", (), id="next_track"),
        pytest.param(
            SERVICE_MEDIA_PREVIOUS_TRACK, {}, "previous", (), id="previous_track"
        ),
        pytest.param(
            SERVICE_MEDIA_SEEK,
            {ATTR_MEDIA_SEEK_POSITION: 42},
            "seek",
            (42,),
            id="seek",
        ),
        pytest.param(
            SERVICE_REPEAT_SET,
            {ATTR_MEDIA_REPEAT: RepeatMode.ONE},
            "set_loop_mode",
            (LoopMode.CONTINOUS_PLAY_ONE_SONG,),
            id="repeat_set",
        ),
    ],
)
async def test_follower_transport_commands_go_to_leader(
    hass: HomeAssistant,
    leader_player: AsyncMock,
    service: str,
    service_data: dict[str, Any],
    method: str,
    method_args: tuple[Any, ...],
) -> None:
    """Test that transport commands on a follower control the group leader."""

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    getattr(leader_player, method).assert_awaited_once_with(*method_args)


@pytest.mark.usefixtures("leader_player")
async def test_group_members_follow_renamed_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test group members report the new entity_id after a rename."""
    entity_to_bridge = hass.data[DOMAIN][SHARED_DATA].entity_to_bridge
    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)

    entity_registry.async_update_entity(ENTITY_ID, new_entity_id=RENAMED_ENTITY_ID)
    await hass.async_block_till_done()

    assert set(entity_to_bridge) == {LEADER_ENTITY_ID, RENAMED_ENTITY_ID}
    state = hass.states.get(RENAMED_ENTITY_ID)
    assert state.attributes[ATTR_GROUP_MEMBERS] == [
        LEADER_ENTITY_ID,
        RENAMED_ENTITY_ID,
    ]
    # The state is written once under the new entity_id, already re-keyed
    assert [
        (
            event.data["old_state"],
            event.data["new_state"].attributes[ATTR_GROUP_MEMBERS],
        )
        for event in state_changes
        if event.data["entity_id"] == RENAMED_ENTITY_ID
    ] == [(None, [LEADER_ENTITY_ID, RENAMED_ENTITY_ID])]

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert set(entity_to_bridge) == {LEADER_ENTITY_ID}


@pytest.mark.usefixtures("leader_player")
async def test_join_renamed_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test joining resolves a renamed player by its new entity_id only."""
    entity_registry.async_update_entity(ENTITY_ID, new_entity_id=RENAMED_ENTITY_ID)
    await hass.async_block_till_done()
    bridge = mock_config_entry.runtime_data.bridge

    with (
        patch.object(LinkPlayMultiroom, "add_follower") as mock_add_follower,
        patch.object(hass.data[DOMAIN][SHARED_DATA].controller, "discover_multirooms"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: RENAMED_ENTITY_ID,
                ATTR_GROUP_MEMBERS: [RENAMED_ENTITY_ID],
            },
            blocking=True,
        )
        mock_add_follower.assert_awaited_once_with(bridge)

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_JOIN,
                {ATTR_ENTITY_ID: RENAMED_ENTITY_ID, ATTR_GROUP_MEMBERS: [ENTITY_ID]},
                blocking=True,
            )
