"""Tests for the Bluesound Media Player platform."""

import dataclasses
from typing import Any
from unittest.mock import patch

from pyblu import PairedPlayer
from pyblu.errors import PlayerUnreachableError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_capture_events
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.bluesound.const import ATTR_MASTER
from homeassistant.components.media_player import (
    ATTR_GROUP_MEMBERS,
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_JOIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SERVICE_SHUFFLE_SET,
    SERVICE_UNJOIN,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    BrowseMedia,
    MediaClass,
    MediaPlayerState,
)
from homeassistant.components.media_source import PlayMedia
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    EVENT_STATE_CHANGED,
    EVENT_STATE_REPORTED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, EventStateReportedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import PlayerMocks


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_MEDIA_PAUSE, "pause"),
        (SERVICE_MEDIA_PLAY, "play"),
        (SERVICE_MEDIA_NEXT_TRACK, "skip"),
        (SERVICE_MEDIA_PREVIOUS_TRACK, "back"),
    ],
)
async def test_simple_actions(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
    service: str,
    method: str,
) -> None:
    """Test the media player simple actions."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "media_player.player_name1111"},
        blocking=True,
    )

    getattr(player_mocks.player_data.player, method).assert_called_once_with()


async def test_volume_set(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player volume set."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: "media_player.player_name1111", ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )

    player_mocks.player_data.player.volume.assert_called_once_with(level=50)


async def test_volume_mute(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player volume mute."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: "media_player.player_name1111", "is_volume_muted": True},
        blocking=True,
    )

    player_mocks.player_data.player.volume.assert_called_once_with(mute=True)


async def test_volume_up(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player volume up."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.volume.assert_called_once_with(level=11)


async def test_volume_down(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player volume down."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.volume.assert_called_once_with(level=9)


@pytest.mark.parametrize(
    ("input", "url"),
    [
        ("input1", "url1"),
        ("input2", "url2"),
        ("input3", "url3"),
        ("4", "url4"),
    ],
)
async def test_select_input_source(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
    input: str,
    url: str,
) -> None:
    """Test the media player select input source."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.player_name1111", ATTR_INPUT_SOURCE: input},
    )

    player_mocks.player_data.player.play_url.assert_called_once_with(url)


async def test_select_preset_source(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media player select preset source."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.player_name1111", ATTR_INPUT_SOURCE: "preset1"},
    )

    player_mocks.player_data.player.load_preset.assert_called_once_with(1)


async def test_attributes_set(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the media player attributes set."""
    state = hass.states.get("media_player.player_name1111")
    assert state == snapshot(
        exclude=props("media_position_updated_at", "media_position")
    )


async def test_stop_maps_to_idle(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media player stop maps to idle."""
    player_mocks.player_data.status_long_polling_mock.set(
        dataclasses.replace(
            player_mocks.player_data.status_long_polling_mock.get(), state="stop"
        )
    )

    # give the long polling loop a chance to update the
    # state; this could be any async call
    await hass.async_block_till_done()

    assert (
        hass.states.get("media_player.player_name1111").state == MediaPlayerState.IDLE
    )


async def test_status_updated(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media player status updated."""
    pre_state = hass.states.get("media_player.player_name1111")
    assert pre_state.state == "playing"
    assert pre_state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.1

    status = player_mocks.player_data.status_long_polling_mock.get()
    status = dataclasses.replace(status, state="pause", volume=50, etag="changed")
    player_mocks.player_data.status_long_polling_mock.set(status)

    # give the long polling loop a chance to update the
    # state; this could be any async call
    await hass.async_block_till_done()

    post_state = hass.states.get("media_player.player_name1111")

    assert post_state.state == MediaPlayerState.PAUSED
    assert post_state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.5


async def test_unavailable_when_offline(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test that the media player goes unavailable when the player is unreachable."""
    pre_state = hass.states.get("media_player.player_name1111")
    assert pre_state.state == "playing"

    player_mocks.player_data.status_long_polling_mock.set_error(
        PlayerUnreachableError("Player not reachable")
    )
    player_mocks.player_data.status_long_polling_mock.trigger()

    # give the long polling loop a chance to update the
    # state; this could be any async call
    await hass.async_block_till_done()

    post_state = hass.states.get("media_player.player_name1111")

    assert post_state.state == STATE_UNAVAILABLE


async def test_attr_master(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media player leader."""
    attr_master = hass.states.get("media_player.player_name1111").attributes[
        ATTR_MASTER
    ]
    assert attr_master is False

    updated_sync_status = dataclasses.replace(
        player_mocks.player_data.sync_status_long_polling_mock.get(),
        followers=[PairedPlayer("2.2.2.2", 11000)],
    )
    player_mocks.player_data.sync_status_long_polling_mock.set(updated_sync_status)

    # give the long polling loop a chance to update the
    # state; this could be any async call
    await hass.async_block_till_done()

    attr_master = hass.states.get("media_player.player_name1111").attributes[
        ATTR_MASTER
    ]

    assert attr_master is True


async def test_attr_bluesound_group(
    hass: HomeAssistant,
    setup_config_entry: None,
    setup_config_entry_secondary: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media player grouping for leader."""
    attr_bluesound_group = hass.states.get(
        "media_player.player_name1111"
    ).attributes.get("bluesound_group")
    assert attr_bluesound_group is None

    updated_sync_status = dataclasses.replace(
        player_mocks.player_data.sync_status_long_polling_mock.get(),
        followers=[PairedPlayer("2.2.2.2", 11000)],
    )
    player_mocks.player_data.sync_status_long_polling_mock.set(updated_sync_status)

    # give the long polling loop a chance to update the
    # state; this could be any async call
    await hass.async_block_till_done()

    attr_bluesound_group = hass.states.get(
        "media_player.player_name1111"
    ).attributes.get("bluesound_group")

    assert attr_bluesound_group == ["player-name1111", "player-name2222"]


async def test_attr_bluesound_group_skips_an_entry_that_is_not_loaded(
    hass: HomeAssistant,
    setup_config_entry: None,
    config_entry_secondary: MockConfigEntry,
    player_mocks: PlayerMocks,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test grouping passes over a player whose entry never loaded.

    Such an entry carries no runtime data to read a sync status from.
    """
    config_entry_secondary.add_to_hass(hass)
    assert config_entry_secondary.state is ConfigEntryState.NOT_LOADED

    updated_sync_status = dataclasses.replace(
        player_mocks.player_data.sync_status_long_polling_mock.get(),
        followers=[PairedPlayer("2.2.2.2", 11000)],
    )
    player_mocks.player_data.sync_status_long_polling_mock.set(updated_sync_status)

    # give the long polling loop a chance to update the
    # state; this could be any async call
    await hass.async_block_till_done()

    assert "runtime_data" not in caplog.text
    assert hass.states.get("media_player.player_name1111") is not None


async def test_attr_bluesound_group_for_follower(
    hass: HomeAssistant,
    setup_config_entry: None,
    setup_config_entry_secondary: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media player grouping for follower."""
    attr_bluesound_group = hass.states.get(
        "media_player.player_name2222"
    ).attributes.get("bluesound_group")
    assert attr_bluesound_group is None

    updated_sync_status = dataclasses.replace(
        player_mocks.player_data.sync_status_long_polling_mock.get(),
        followers=[PairedPlayer("2.2.2.2", 11000)],
    )
    player_mocks.player_data.sync_status_long_polling_mock.set(updated_sync_status)

    # give the long polling loop a chance to update the
    # state; this could be any async call
    await hass.async_block_till_done()

    updated_sync_status = dataclasses.replace(
        player_mocks.player_data_secondary.sync_status_long_polling_mock.get(),
        leader=PairedPlayer("1.1.1.1", 11000),
    )
    player_mocks.player_data_secondary.sync_status_long_polling_mock.set(
        updated_sync_status
    )

    # give the long polling loop a chance to update the
    # state; this could be any async call
    await hass.async_block_till_done()

    attr_bluesound_group = hass.states.get(
        "media_player.player_name2222"
    ).attributes.get("bluesound_group")

    assert attr_bluesound_group == ["player-name1111", "player-name2222"]


async def test_volume_up_from_6_to_7(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media player volume up from 6 to 7.

    This fails if rounding is not done correctly. See
    https://github.com/home-assistant/core/issues/129956
    for more details.
    """
    player_mocks.player_data.status_long_polling_mock.set(
        dataclasses.replace(
            player_mocks.player_data.status_long_polling_mock.get(), volume=6
        )
    )

    # give the long polling loop a chance to update the
    # state; this could be any async call
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.volume.assert_called_once_with(level=7)


async def test_attr_group_members(
    hass: HomeAssistant,
    setup_config_entry: None,
    setup_config_entry_secondary: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media player grouping for leader."""
    attr_group_members = hass.states.get("media_player.player_name1111").attributes.get(
        ATTR_GROUP_MEMBERS
    )
    assert attr_group_members is None

    updated_sync_status = dataclasses.replace(
        player_mocks.player_data.sync_status_long_polling_mock.get(),
        followers=[PairedPlayer("2.2.2.2", 11000)],
    )
    player_mocks.player_data.sync_status_long_polling_mock.set(updated_sync_status)

    # give the long polling loop a chance to update the
    # state; this could be any async call
    await hass.async_block_till_done()

    attr_group_members = hass.states.get("media_player.player_name1111").attributes.get(
        ATTR_GROUP_MEMBERS
    )

    assert attr_group_members == [
        "media_player.player_name1111",
        "media_player.player_name2222",
    ]


@pytest.mark.parametrize(
    ("renamed_entity_id", "leader_entity_id", "follower_entity_id"),
    [
        pytest.param(
            "media_player.player_name1111",
            "media_player.renamed",
            "media_player.player_name2222",
            id="leader",
        ),
        pytest.param(
            "media_player.player_name2222",
            "media_player.player_name1111",
            "media_player.renamed",
            id="follower",
        ),
    ],
)
async def test_attr_group_members_after_entity_id_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_config_entry: None,
    setup_config_entry_secondary: None,
    player_mocks: PlayerMocks,
    renamed_entity_id: str,
    leader_entity_id: str,
    follower_entity_id: str,
) -> None:
    """Test the leader's group members follow an entity_id change of a member."""
    updated_sync_status = dataclasses.replace(
        player_mocks.player_data.sync_status_long_polling_mock.get(),
        followers=[PairedPlayer("2.2.2.2", 11000)],
    )
    player_mocks.player_data.sync_status_long_polling_mock.set(updated_sync_status)
    await hass.async_block_till_done()
    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    state_reports: list[Event[EventStateReportedData]] = []

    @callback
    def _is_renamed(data: EventStateReportedData) -> bool:
        return data["entity_id"] == "media_player.renamed"

    @callback
    def _capture_report(event: Event[EventStateReportedData]) -> None:
        state_reports.append(event)

    hass.bus.async_listen(
        EVENT_STATE_REPORTED, _capture_report, event_filter=_is_renamed
    )

    entity_registry.async_update_entity(
        renamed_entity_id, new_entity_id="media_player.renamed"
    )
    await hass.async_block_till_done()

    attr_group_members = hass.states.get(leader_entity_id).attributes.get(
        ATTR_GROUP_MEMBERS
    )
    assert attr_group_members == [leader_entity_id, follower_entity_id]
    # The renamed player's state is written once under the new entity_id; a
    # repeated identical write would be a state report
    assert [
        event.data["old_state"]
        for event in state_changes
        if event.data["entity_id"] == "media_player.renamed"
    ] == [None]
    assert not state_reports


async def test_join_players(
    hass: HomeAssistant,
    setup_config_entry: None,
    setup_config_entry_secondary: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media_player.join action."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_JOIN,
        {
            ATTR_ENTITY_ID: "media_player.player_name1111",
            ATTR_GROUP_MEMBERS: "media_player.player_name2222",
        },
        blocking=True,
    )

    player_mocks.player_data.player.add_followers.assert_called_once_with(
        [PairedPlayer("2.2.2.2", 11000)]
    )


async def test_join_players_after_entity_id_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_config_entry: None,
    setup_config_entry_secondary: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media_player.join action follows an entity_id change of a member."""
    entity_registry.async_update_entity(
        "media_player.player_name2222", new_entity_id="media_player.renamed_member"
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_JOIN,
        {
            ATTR_ENTITY_ID: "media_player.player_name1111",
            ATTR_GROUP_MEMBERS: "media_player.player_name2222",
        },
        blocking=True,
    )
    player_mocks.player_data.player.add_followers.assert_not_called()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_JOIN,
        {
            ATTR_ENTITY_ID: "media_player.player_name1111",
            ATTR_GROUP_MEMBERS: "media_player.renamed_member",
        },
        blocking=True,
    )
    player_mocks.player_data.player.add_followers.assert_called_once_with(
        [PairedPlayer("2.2.2.2", 11000)]
    )


async def test_join_player_cannot_join_to_self(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test that joining to self is not allowed."""
    with pytest.raises(ServiceValidationError, match="Cannot join player to itself"):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: "media_player.player_name1111",
                ATTR_GROUP_MEMBERS: "media_player.player_name1111",
            },
            blocking=True,
        )


async def test_unjoin_player(
    hass: HomeAssistant,
    setup_config_entry: None,
    setup_config_entry_secondary: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the media_player.unjoin action."""
    updated_sync_status = dataclasses.replace(
        player_mocks.player_data.sync_status_long_polling_mock.get(),
        leader=PairedPlayer("2.2.2.2", 11000),
    )
    player_mocks.player_data.sync_status_long_polling_mock.set(updated_sync_status)

    # give the long polling loop a chance to update the
    # state; this could be any async call
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_UNJOIN,
        {ATTR_ENTITY_ID: "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data_secondary.player.remove_follower.assert_called_once_with(
        "1.1.1.1", 11000
    )


@pytest.mark.usefixtures("setup_config_entry", "setup_config_entry_secondary")
@pytest.mark.parametrize(
    ("leader", "message"),
    [
        pytest.param(
            PairedPlayer("2.2.2.2", 11000),
            "Could not reach the Bluesound player: timeout",
            id="leader_unreachable",
        ),
        pytest.param(
            PairedPlayer("3.3.3.3", 11000),
            "The group leader 3.3.3.3:11000 is not set up in Home Assistant",
            id="leader_not_loaded",
        ),
    ],
)
async def test_unjoin_player_error(
    hass: HomeAssistant,
    player_mocks: PlayerMocks,
    leader: PairedPlayer,
    message: str,
) -> None:
    """Test that a failing unjoin raises HomeAssistantError."""
    player_mocks.player_data_secondary.player.remove_follower.side_effect = (
        PlayerUnreachableError("timeout")
    )
    updated_sync_status = dataclasses.replace(
        player_mocks.player_data.sync_status_long_polling_mock.get(),
        leader=leader,
    )
    player_mocks.player_data.sync_status_long_polling_mock.set(updated_sync_status)

    # give the long polling loop a chance to update the
    # state; this could be any async call
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_UNJOIN,
            {ATTR_ENTITY_ID: "media_player.player_name1111"},
            blocking=True,
        )


@pytest.mark.usefixtures("setup_config_entry", "setup_config_entry_secondary")
@pytest.mark.parametrize(
    ("service", "service_data", "method"),
    [
        pytest.param(SERVICE_MEDIA_PLAY, {}, "play", id="play"),
        pytest.param(SERVICE_MEDIA_PAUSE, {}, "pause", id="pause"),
        pytest.param(SERVICE_MEDIA_STOP, {}, "stop", id="stop"),
        pytest.param(SERVICE_MEDIA_NEXT_TRACK, {}, "skip", id="next_track"),
        pytest.param(SERVICE_MEDIA_PREVIOUS_TRACK, {}, "back", id="previous_track"),
        pytest.param(SERVICE_CLEAR_PLAYLIST, {}, "clear", id="clear_playlist"),
        pytest.param(
            SERVICE_SHUFFLE_SET, {ATTR_MEDIA_SHUFFLE: True}, "shuffle", id="shuffle"
        ),
        pytest.param(
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "input1"},
            "play_url",
            id="select_input",
        ),
        pytest.param(
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "preset1"},
            "load_preset",
            id="select_preset",
        ),
        pytest.param(
            SERVICE_PLAY_MEDIA,
            {
                ATTR_MEDIA_CONTENT_TYPE: "music",
                ATTR_MEDIA_CONTENT_ID: "http://example.com/song.mp3",
            },
            "play_url",
            id="play_media",
        ),
        pytest.param(
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
            "volume",
            id="volume_set",
        ),
        pytest.param(
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: True},
            "volume",
            id="volume_mute",
        ),
        pytest.param(
            SERVICE_JOIN,
            {ATTR_GROUP_MEMBERS: "media_player.player_name2222"},
            "add_followers",
            id="join",
        ),
    ],
)
async def test_action_error(
    hass: HomeAssistant,
    player_mocks: PlayerMocks,
    service: str,
    service_data: dict[str, Any],
    method: str,
) -> None:
    """Test that a failing player call raises HomeAssistantError."""
    getattr(
        player_mocks.player_data.player, method
    ).side_effect = PlayerUnreachableError("timeout")

    with pytest.raises(
        HomeAssistantError, match="Could not reach the Bluesound player: timeout"
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "media_player.player_name1111", **service_data},
            blocking=True,
        )


async def test_media_image_relative_url(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a relative image url is fetched from the player."""
    aioclient_mock.get("http://1.1.1.1:11000/Artwork", content=b"image")
    player_mocks.player_data.status_long_polling_mock.set(
        dataclasses.replace(
            player_mocks.player_data.status_long_polling_mock.get(), image="/Artwork"
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get("media_player.player_name1111")
    client = await hass_client()
    response = await client.get(state.attributes[ATTR_ENTITY_PICTURE])

    assert await response.read() == b"image"


async def test_media_position_and_duration_unknown(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test position and duration are not set when the player does not report them."""
    player_mocks.player_data.status_long_polling_mock.set(
        dataclasses.replace(
            player_mocks.player_data.status_long_polling_mock.get(),
            seconds=None,
            total_seconds=None,
        )
    )
    await hass.async_block_till_done()

    attributes = hass.states.get("media_player.player_name1111").attributes
    assert ATTR_MEDIA_POSITION not in attributes
    assert ATTR_MEDIA_DURATION not in attributes


@pytest.mark.parametrize(
    ("input_id", "stream_url", "source"),
    [
        pytest.param("1", None, "input1", id="input_by_id"),
        pytest.param("unknown", "url3", "input3", id="input_by_url"),
        pytest.param("4", None, "4", id="input_without_text"),
        pytest.param(None, "url2", "preset2", id="preset"),
    ],
)
async def test_source(
    hass: HomeAssistant,
    setup_config_entry: None,
    player_mocks: PlayerMocks,
    input_id: str | None,
    stream_url: str | None,
    source: str,
) -> None:
    """Test the current source is matched to an input or preset."""
    player_mocks.player_data.status_long_polling_mock.set(
        dataclasses.replace(
            player_mocks.player_data.status_long_polling_mock.get(),
            input_id=input_id,
            stream_url=stream_url,
        )
    )
    await hass.async_block_till_done()

    assert (
        hass.states.get("media_player.player_name1111").attributes[ATTR_INPUT_SOURCE]
        == source
    )


async def test_select_unknown_source(
    hass: HomeAssistant, setup_config_entry: None
) -> None:
    """Test selecting an unknown source raises an error."""
    with pytest.raises(ServiceValidationError, match="Source unknown not found"):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {
                ATTR_ENTITY_ID: "media_player.player_name1111",
                ATTR_INPUT_SOURCE: "unknown",
            },
            blocking=True,
        )


async def test_media_seek(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test seeking when the player supports it."""
    player_mocks.player_data.status_long_polling_mock.set(
        dataclasses.replace(
            player_mocks.player_data.status_long_polling_mock.get(), can_seek=True
        )
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_SEEK,
        {ATTR_ENTITY_ID: "media_player.player_name1111", ATTR_MEDIA_SEEK_POSITION: 30},
        blocking=True,
    )

    player_mocks.player_data.player.play.assert_called_once_with(seek=30)


async def test_unjoin_player_as_leader(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the media_player.unjoin action on a group leader."""
    player_mocks.player_data.sync_status_long_polling_mock.set(
        dataclasses.replace(
            player_mocks.player_data.sync_status_long_polling_mock.get(),
            followers=[PairedPlayer("2.2.2.2", 11000)],
        )
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_UNJOIN,
        {ATTR_ENTITY_ID: "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.remove_follower.assert_called_once_with(
        "1.1.1.1", 11000
    )


async def test_play_media_source(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test playing a media source item plays its resolved url."""
    with patch(
        "homeassistant.components.bluesound.media_player.media_source.async_resolve_media",
        return_value=PlayMedia(
            url="http://example.com/song.mp3", mime_type="audio/mpeg"
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.player_name1111",
                ATTR_MEDIA_CONTENT_TYPE: "music",
                ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/song.mp3",
            },
            blocking=True,
        )

    player_mocks.player_data.player.play_url.assert_called_once_with(
        "http://example.com/song.mp3"
    )


async def test_browse_media(
    hass: HomeAssistant,
    setup_config_entry: None,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test browsing media is delegated to media source."""
    with patch(
        "homeassistant.components.bluesound.media_player.media_source.async_browse_media",
        return_value=BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id="media-source://media_source",
            media_content_type="",
            title="Media",
            can_play=False,
            can_expand=True,
        ),
    ):
        client = await hass_ws_client()
        await client.send_json_auto_id(
            {
                "type": "media_player/browse_media",
                "entity_id": "media_player.player_name1111",
            }
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"]["title"] == "Media"
