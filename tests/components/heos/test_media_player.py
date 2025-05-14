"""Tests for the Heos Media Player platform."""

from datetime import timedelta
import re
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from pyheos import (
    AddCriteriaType,
    BrowseResult,
    CommandFailedError,
    HeosError,
    MediaItem,
    MediaMusicSource,
    MediaType as HeosMediaType,
    PlayerUpdateResult,
    PlayState,
    QueueItem,
    RepeatType,
    SignalHeosEvent,
    SignalType,
    const,
)
from pyheos.util import mediauri
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.heos.const import (
    ATTR_DESTINATION_POSITION,
    ATTR_QUEUE_IDS,
    DOMAIN,
    SERVICE_GET_QUEUE,
    SERVICE_GROUP_VOLUME_DOWN,
    SERVICE_GROUP_VOLUME_SET,
    SERVICE_GROUP_VOLUME_UP,
    SERVICE_MOVE_QUEUE_ITEM,
    SERVICE_REMOVE_FROM_QUEUE,
)
from homeassistant.components.media_player import (
    ATTR_GROUP_MEMBERS,
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_JOIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SERVICE_UNJOIN,
    MediaType,
    RepeatMode,
)
from homeassistant.components.media_source import DOMAIN as MS_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_IDLE,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import MockHeos

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.conftest import async_setup_component
from tests.typing import WebSocketGenerator


async def test_state_attributes(
    hass: HomeAssistant, config_entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Tests the state attributes."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    state = hass.states.get("media_player.test_player")
    assert state == snapshot(
        exclude=props(
            "entity_picture_local",
            "context",
            "last_changed",
            "last_reported",
            "last_updated",
        )
    )


async def test_updates_from_signals(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Tests dispatched signals update player."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]

    # Test player does not update for other players
    player.state = PlayState.PLAY
    await controller.dispatcher.wait_send(
        SignalType.PLAYER_EVENT, 2, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.state == STATE_IDLE

    # Test player_update standard events
    player.state = PlayState.PLAY
    await controller.dispatcher.wait_send(
        SignalType.PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()

    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.state == STATE_PLAYING

    # Test player_update progress events
    player.now_playing_media.duration = 360000
    player.now_playing_media.current_position = 1000
    await controller.dispatcher.wait_send(
        SignalType.PLAYER_EVENT,
        player.player_id,
        const.EVENT_PLAYER_NOW_PLAYING_PROGRESS,
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] is not None
    assert state.attributes[ATTR_MEDIA_DURATION] == 360
    assert state.attributes[ATTR_MEDIA_POSITION] == 1


async def test_updates_from_connection_event(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests player updates from connection event after connection failure."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]

    # Connected
    player.available = True
    await controller.dispatcher.wait_send(
        SignalType.HEOS_EVENT, SignalHeosEvent.CONNECTED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.state == STATE_IDLE

    # Disconnected
    controller.load_players.reset_mock()
    player.available = False
    await controller.dispatcher.wait_send(
        SignalType.HEOS_EVENT, SignalHeosEvent.DISCONNECTED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Reconnect and state updates
    player.available = True
    await controller.dispatcher.wait_send(
        SignalType.HEOS_EVENT, SignalHeosEvent.CONNECTED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.state == STATE_IDLE


async def test_updates_from_sources_updated(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Tests player updates from changes in sources list."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    controller.get_input_sources.return_value = []
    await controller.dispatcher.wait_send(
        SignalType.CONTROLLER_EVENT, const.EVENT_SOURCES_CHANGED, {}
    )
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == [
        "Today's Hits Radio",
        "Classical MPR (Classical Music)",
    ]


async def test_updates_from_players_changed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    change_data: PlayerUpdateResult,
) -> None:
    """Test player updates from changes to available players."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]

    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.state == STATE_IDLE
    player.state = PlayState.PLAY
    await controller.dispatcher.wait_send(
        SignalType.CONTROLLER_EVENT, const.EVENT_PLAYERS_CHANGED, change_data
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.state == STATE_PLAYING


async def test_updates_from_players_changed_new_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    change_data_mapped_ids: PlayerUpdateResult,
) -> None:
    """Test player updates from changes to available players."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    # Assert device registry matches current id
    assert device_registry.async_get_device(identifiers={(DOMAIN, "1")})
    # Assert entity registry matches current id
    assert (
        entity_registry.async_get_entity_id(MEDIA_PLAYER_DOMAIN, DOMAIN, "1")
        == "media_player.test_player"
    )

    await controller.dispatcher.wait_send(
        SignalType.CONTROLLER_EVENT,
        const.EVENT_PLAYERS_CHANGED,
        change_data_mapped_ids,
    )
    await hass.async_block_till_done()

    # Assert device registry identifiers were updated
    assert len(device_registry.devices) == 2
    assert device_registry.async_get_device(identifiers={(DOMAIN, "101")})
    # Assert entity registry unique id was updated
    assert len(entity_registry.entities) == 2
    assert (
        entity_registry.async_get_entity_id(MEDIA_PLAYER_DOMAIN, DOMAIN, "101")
        == "media_player.test_player"
    )


async def test_updates_from_user_changed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Tests player updates from changes in user."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    controller.mock_set_signed_in_username(None)
    await controller.dispatcher.wait_send(
        SignalType.CONTROLLER_EVENT, const.EVENT_USER_CHANGED, None
    )
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == [
        "HEOS Drive - Line In 1",
        "Speaker - Line In 1",
    ]


async def test_updates_from_groups_changed(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test player updates from changes to groups."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Assert current state
    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.attributes[ATTR_GROUP_MEMBERS] == [
        "media_player.test_player",
        "media_player.test_player_2",
    ]
    state = hass.states.get("media_player.test_player_2")
    assert state is not None
    assert state.attributes[ATTR_GROUP_MEMBERS] == [
        "media_player.test_player",
        "media_player.test_player_2",
    ]

    # Clear group information
    controller.mock_set_groups({})
    for player in controller.players.values():
        player.group_id = None
    await controller.dispatcher.wait_send(
        SignalType.CONTROLLER_EVENT, const.EVENT_GROUPS_CHANGED, None
    )
    await hass.async_block_till_done()

    # Assert groups changed
    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.attributes[ATTR_GROUP_MEMBERS] is None

    state = hass.states.get("media_player.test_player_2")
    assert state is not None
    assert state.attributes[ATTR_GROUP_MEMBERS] is None


async def test_clear_playlist(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the clear playlist service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_CLEAR_PLAYLIST,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    assert controller.player_clear_queue.call_count == 1


async def test_clear_playlist_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test error raised when clear playlist fails."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.player_clear_queue.side_effect = CommandFailedError("", "Failure", 1)
    with pytest.raises(
        HomeAssistantError, match=re.escape("Unable to clear playlist: Failure (1)")
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_CLEAR_PLAYLIST,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
    assert controller.player_clear_queue.call_count == 1


async def test_pause(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the pause service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    assert controller.player_set_play_state.call_count == 1


async def test_pause_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the pause service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.player_set_play_state.side_effect = CommandFailedError("", "Failure", 1)
    with pytest.raises(
        HomeAssistantError, match=re.escape("Unable to pause: Failure (1)")
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PAUSE,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
    assert controller.player_set_play_state.call_count == 1


async def test_play(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the play service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    assert controller.player_set_play_state.call_count == 1


async def test_play_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the play service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.player_set_play_state.side_effect = CommandFailedError("", "Failure", 1)
    with pytest.raises(
        HomeAssistantError, match=re.escape("Unable to play: Failure (1)")
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PLAY,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
    assert controller.player_set_play_state.call_count == 1


async def test_previous_track(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the previous track service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    assert controller.player_play_previous.call_count == 1


async def test_previous_track_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the previous track service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.player_play_previous.side_effect = CommandFailedError("", "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to move to previous track: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
    assert controller.player_play_previous.call_count == 1


async def test_next_track(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the next track service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_NEXT_TRACK,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    assert controller.player_play_next.call_count == 1


async def test_next_track_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the next track service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.player_play_next.side_effect = CommandFailedError("", "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to move to next track: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
    assert controller.player_play_next.call_count == 1


async def test_stop(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the stop service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    assert controller.player_set_play_state.call_count == 1


async def test_stop_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the stop service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.player_set_play_state.side_effect = CommandFailedError("", "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to stop: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_STOP,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
    assert controller.player_set_play_state.call_count == 1


async def test_volume_mute(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the volume mute service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    assert controller.player_set_mute.call_count == 1


async def test_volume_mute_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the volume mute service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.player_set_mute.side_effect = CommandFailedError("", "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to set mute: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_MUTE,
            {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_MUTED: True},
            blocking=True,
        )
    assert controller.player_set_mute.call_count == 1


async def test_shuffle_set(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the shuffle set service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SHUFFLE_SET,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_SHUFFLE: True},
        blocking=True,
    )
    controller.player_set_play_mode.assert_called_once_with(1, player.repeat, True)


async def test_shuffle_set_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the shuffle set service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    controller.player_set_play_mode.side_effect = CommandFailedError("", "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to set shuffle: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SHUFFLE_SET,
            {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_SHUFFLE: True},
            blocking=True,
        )
    controller.player_set_play_mode.assert_called_once_with(1, player.repeat, True)


async def test_repeat_set(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the repeat set service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_REPEAT: RepeatMode.ONE},
        blocking=True,
    )
    controller.player_set_play_mode.assert_called_once_with(
        1, RepeatType.ON_ONE, player.shuffle
    )


async def test_repeat_set_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the repeat set service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    controller.player_set_play_mode.side_effect = CommandFailedError("", "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to set repeat: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_REPEAT_SET,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_REPEAT: RepeatMode.ALL,
            },
            blocking=True,
        )
    controller.player_set_play_mode.assert_called_once_with(
        1, RepeatType.ON_ALL, player.shuffle
    )


async def test_volume_set(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the volume set service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_LEVEL: 1},
        blocking=True,
    )
    controller.player_set_volume.assert_called_once_with(1, 100)


async def test_volume_set_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the volume set service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.player_set_volume.side_effect = CommandFailedError("", "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to set volume level: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_SET,
            {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_LEVEL: 1},
            blocking=True,
        )
    controller.player_set_volume.assert_called_once_with(1, 100)


async def test_group_volume_set(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the group volume set service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GROUP_VOLUME_SET,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_LEVEL: 1},
        blocking=True,
    )
    controller.set_group_volume.assert_called_once_with(999, 100)


async def test_group_volume_set_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the group volume set service errors."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.set_group_volume.side_effect = CommandFailedError("", "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to set group volume level: Failure (1)"),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GROUP_VOLUME_SET,
            {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_LEVEL: 1},
            blocking=True,
        )
    controller.set_group_volume.assert_called_once_with(999, 100)


async def test_group_volume_set_not_grouped_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the group volume set service when not grouped raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    player.group_id = None
    with pytest.raises(
        ServiceValidationError,
        match=re.escape("Entity media_player.test_player is not joined to a group"),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GROUP_VOLUME_SET,
            {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_LEVEL: 1},
            blocking=True,
        )
    controller.set_group_volume.assert_not_called()


async def test_group_volume_down(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the group volume down service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GROUP_VOLUME_DOWN,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    controller.group_volume_down.assert_called_with(999)


async def test_group_volume_up(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the group volume up service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GROUP_VOLUME_UP,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    controller.group_volume_up.assert_called_with(999)


@pytest.mark.parametrize(
    "service", [SERVICE_GROUP_VOLUME_DOWN, SERVICE_GROUP_VOLUME_UP]
)
async def test_group_volume_down_up_ungrouped_raises(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    service: str,
) -> None:
    """Test the group volume down and up service raise if player ungrouped."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    player.group_id = None
    with pytest.raises(
        ServiceValidationError,
        match=re.escape("Entity media_player.test_player is not joined to a group"),
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
    controller.group_volume_down.assert_not_called()
    controller.group_volume_up.assert_not_called()


async def test_select_favorite(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    favorites: dict[int, MediaItem],
) -> None:
    """Tests selecting a music service favorite and state."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # Test set music service preset
    favorite = favorites[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_INPUT_SOURCE: favorite.name},
        blocking=True,
    )
    controller.play_preset_station.assert_called_once_with(1, 1)
    # Test state is matched by station name
    player.now_playing_media.type = HeosMediaType.STATION
    player.now_playing_media.station = favorite.name
    await controller.dispatcher.wait_send(
        SignalType.PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE] == favorite.name


async def test_select_radio_favorite(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    favorites: dict[int, MediaItem],
) -> None:
    """Tests selecting a radio favorite and state."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # Test set radio preset
    favorite = favorites[2]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_INPUT_SOURCE: favorite.name},
        blocking=True,
    )
    controller.play_preset_station.assert_called_once_with(1, 2)
    # Test state is matched by album id
    player.now_playing_media.type = HeosMediaType.STATION
    player.now_playing_media.station = "Classical"
    player.now_playing_media.album_id = favorite.media_id
    await controller.dispatcher.wait_send(
        SignalType.PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE] == favorite.name


async def test_select_radio_favorite_command_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    favorites: dict[int, MediaItem],
) -> None:
    """Tests command error raises when playing favorite."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    # Test set radio preset
    favorite = favorites[2]
    controller.play_preset_station.side_effect = CommandFailedError("", "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to select source: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_INPUT_SOURCE: favorite.name,
            },
            blocking=True,
        )
    controller.play_preset_station.assert_called_once_with(1, 2)


@pytest.mark.parametrize(
    ("source_name", "station"),
    [
        ("HEOS Drive - Line In 1", "Line In 1"),
        ("Speaker - Line In 1", "Speaker - Line In 1"),
    ],
)
async def test_select_input_source(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    input_sources: list[MediaItem],
    source_name: str,
    station: str,
) -> None:
    """Tests selecting input source and state."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_INPUT_SOURCE: source_name,
        },
        blocking=True,
    )
    input_source = next(
        input_sources
        for input_sources in input_sources
        if input_sources.name == source_name
    )
    controller.play_media.assert_called_once_with(
        1, input_source, AddCriteriaType.PLAY_NOW
    )
    # Update the now_playing_media to reflect play_media
    player.now_playing_media.source_id = const.MUSIC_SOURCE_AUX_INPUT
    player.now_playing_media.station = station
    player.now_playing_media.media_id = const.INPUT_AUX_IN_1
    await controller.dispatcher.wait_send(
        SignalType.PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE] == source_name


async def test_select_input_unknown_raises(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Tests selecting an unknown input raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    with pytest.raises(
        ServiceValidationError,
        match=re.escape("Unknown source: Unknown"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: "media_player.test_player", ATTR_INPUT_SOURCE: "Unknown"},
            blocking=True,
        )


async def test_select_input_command_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    input_sources: list[MediaItem],
) -> None:
    """Tests selecting an unknown input."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    input_source = input_sources[0]
    controller.play_media.side_effect = CommandFailedError("", "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to select source: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_INPUT_SOURCE: input_source.name,
            },
            blocking=True,
        )
    controller.play_media.assert_called_once_with(
        1, input_source, AddCriteriaType.PLAY_NOW
    )


async def test_unload_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the player is set unavailable when the config entry is unloaded."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    state = hass.states.get("media_player.test_player")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("media_type", [MediaType.URL, MediaType.MUSIC])
async def test_play_media(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    media_type: MediaType,
) -> None:
    """Test the play media service with type url."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    url = "http://news/podcast.mp3"
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: url,
        },
        blocking=True,
    )
    controller.play_url.assert_called_once_with(1, url)


@pytest.mark.parametrize("media_type", [MediaType.URL, MediaType.MUSIC])
async def test_play_media_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    media_type: MediaType,
) -> None:
    """Test the play media service with type url error raises."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.play_url.side_effect = CommandFailedError("", "Failure", 1)
    url = "http://news/podcast.mp3"
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to play media: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_TYPE: media_type,
                ATTR_MEDIA_CONTENT_ID: url,
            },
            blocking=True,
        )
    controller.play_url.assert_called_once_with(1, url)


@pytest.mark.parametrize(
    ("content_id", "expected_index"), [("1", 1), ("Quick Select 2", 2)]
)
async def test_play_media_quick_select(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    content_id: str,
    expected_index: int,
) -> None:
    """Test the play media service with type quick_select."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: "quick_select",
            ATTR_MEDIA_CONTENT_ID: content_id,
        },
        blocking=True,
    )
    controller.player_play_quick_select.assert_called_once_with(1, expected_index)


async def test_play_media_quick_select_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the play media service with invalid quick_select raises."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to play media: Invalid quick select 'Invalid'"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_TYPE: "quick_select",
                ATTR_MEDIA_CONTENT_ID: "Invalid",
            },
            blocking=True,
        )
    assert controller.player_play_quick_select.call_count == 0


@pytest.mark.parametrize(
    ("enqueue", "criteria"),
    [
        (None, AddCriteriaType.REPLACE_AND_PLAY),
        (True, AddCriteriaType.ADD_TO_END),
        ("next", AddCriteriaType.PLAY_NEXT),
    ],
)
async def test_play_media_playlist(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    playlists: list[MediaItem],
    enqueue: Any,
    criteria: AddCriteriaType,
) -> None:
    """Test the play media service with type playlist."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    playlist = playlists[0]
    service_data = {
        ATTR_ENTITY_ID: "media_player.test_player",
        ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
        ATTR_MEDIA_CONTENT_ID: playlist.name,
    }
    if enqueue is not None:
        service_data[ATTR_MEDIA_ENQUEUE] = enqueue
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        service_data,
        blocking=True,
    )
    controller.play_media.assert_called_once_with(1, playlist, criteria)


async def test_play_media_playlist_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the play media service with an invalid playlist name."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to play media: Invalid playlist 'Invalid'"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
                ATTR_MEDIA_CONTENT_ID: "Invalid",
            },
            blocking=True,
        )
    assert controller.add_to_queue.call_count == 0


@pytest.mark.parametrize(
    ("content_id", "expected_index"), [("1", 1), ("Classical MPR (Classical Music)", 2)]
)
async def test_play_media_favorite(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    content_id: str,
    expected_index: int,
) -> None:
    """Test the play media service with type favorite."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: "favorite",
            ATTR_MEDIA_CONTENT_ID: content_id,
        },
        blocking=True,
    )
    controller.play_preset_station.assert_called_once_with(1, expected_index)


async def test_play_media_favorite_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the play media service with an invalid favorite raises."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to play media: Invalid favorite 'Invalid'"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_TYPE: "favorite",
                ATTR_MEDIA_CONTENT_ID: "Invalid",
            },
            blocking=True,
        )
    assert controller.play_preset_station.call_count == 0


async def test_play_media_invalid_type(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the play media service with an invalid type."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to play media: Unsupported media type 'Other'"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_TYPE: "Other",
                ATTR_MEDIA_CONTENT_ID: "",
            },
            blocking=True,
        )


async def test_play_media_media_uri(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    playlist: MediaItem,
) -> None:
    """Test the play media service with HEOS media uri."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    media_content_id = mediauri.to_media_uri(playlist)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_ID: media_content_id,
            ATTR_MEDIA_CONTENT_TYPE: "",
        },
        blocking=True,
    )
    controller.play_media.assert_called_once()


async def test_play_media_media_uri_invalid(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
) -> None:
    """Test the play media service with an invalid HEOS media uri raises."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    media_id = "heos://media/1/music_service?name=Pandora&available=False&image_url="

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Unable to play media: Invalid media id '{media_id}'"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_ID: media_id,
                ATTR_MEDIA_CONTENT_TYPE: "",
            },
            blocking=True,
        )
    controller.play_media.assert_not_called()


async def test_play_media_music_source_url(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
) -> None:
    """Test the play media service with a music source url."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await async_setup_component(hass, MS_DOMAIN, {MS_DOMAIN: {}})

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/test.mp3",
            ATTR_MEDIA_CONTENT_TYPE: "",
        },
        blocking=True,
    )
    controller.play_url.assert_called_once()


async def test_play_media_queue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
) -> None:
    """Test the play media service with type queue."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: "queue",
            ATTR_MEDIA_CONTENT_ID: "2",
        },
        blocking=True,
    )
    controller.player_play_queue.assert_called_once_with(1, 2)


async def test_play_media_queue_invalid(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the play media service with an invalid queue id."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to play media: Invalid queue id 'Invalid'"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_TYPE: "queue",
                ATTR_MEDIA_CONTENT_ID: "Invalid",
            },
            blocking=True,
        )
    assert controller.player_play_queue.call_count == 0


async def test_browse_media_root(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    music_sources: dict[int, MediaMusicSource],
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing the root."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await async_setup_component(hass, MS_DOMAIN, {MS_DOMAIN: {}})

    controller.mock_set_music_sources(music_sources)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.test_player",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == snapshot


async def test_browse_media_root_no_media_source(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    music_sources: dict[int, MediaMusicSource],
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing the root."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.mock_set_music_sources(music_sources)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.test_player",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == snapshot


async def test_browse_media_root_source_error_continues(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing the root with an error getting sources continues."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.get_music_sources.side_effect = HeosError("error")

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.test_player",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == snapshot
    assert "Unable to load music sources" in caplog.text


async def test_browse_media_heos_media(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    hass_ws_client: WebSocketGenerator,
    pandora_browse_result: BrowseResult,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing a heos media item."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.browse_media.return_value = pandora_browse_result

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.test_player",
            "media_content_id": "heos://media/1/music_service?name=Pandora&image_url=&available=True&service_username=user",
            "media_content_type": "",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == snapshot


async def test_browse_media_heos_media_error_returns_empty(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing a heos media item results in an error, returns empty children."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.browse_media.side_effect = HeosError("error")

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.test_player",
            "media_content_id": "heos://media/1/music_service?name=Pandora&image_url=&available=True&service_username=user",
            "media_content_type": "",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == snapshot
    assert "Unable to browse media" in caplog.text


async def test_browse_media_media_source(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing a media source."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await async_setup_component(hass, MS_DOMAIN, {MS_DOMAIN: {}})

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.test_player",
            "media_content_id": "media-source://media_source/local/.",
            "media_content_type": "",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == snapshot


async def test_browse_media_invalid_content_id(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test browsing an invalid content id fails."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.test_player",
            "media_content_id": "invalid",
            "media_content_type": "",
        }
    )
    response = await client.receive_json()
    assert not response["success"]


@pytest.mark.parametrize(
    ("members", "expected"),
    [
        (["media_player.test_player_2"], [1, 2]),
        (["media_player.test_player_2", "media_player.test_player"], [1, 2]),
        (["media_player.test_player"], [1]),
    ],
)
async def test_media_player_join_group(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    members: list[str],
    expected: tuple[int, list[int]],
) -> None:
    """Test grouping of media players through the join service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_JOIN,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_GROUP_MEMBERS: members,
        },
        blocking=True,
    )
    controller.set_group.assert_called_once_with(expected)


async def test_media_player_join_group_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test grouping of media players through the join service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.set_group.side_effect = HeosError("error")
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to join players: error"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_GROUP_MEMBERS: ["media_player.test_player_2"],
            },
            blocking=True,
        )


async def test_media_player_group_members(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test group_members attribute."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    player_entity = hass.states.get("media_player.test_player")
    assert player_entity is not None
    assert player_entity.attributes[ATTR_GROUP_MEMBERS] == [
        "media_player.test_player",
        "media_player.test_player_2",
    ]
    controller.get_groups.assert_called_once()
    assert "Unable to get HEOS group info" not in caplog.text


async def test_media_player_group_members_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error in HEOS API."""
    controller.mock_set_groups({})
    controller.get_groups.side_effect = HeosError("error")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert "Unable to retrieve groups" in caplog.text
    player_entity = hass.states.get("media_player.test_player")
    assert player_entity is not None
    assert player_entity.attributes[ATTR_GROUP_MEMBERS] is None


@pytest.mark.parametrize(
    ("entity_id", "expected_args"),
    [("media_player.test_player", [1]), ("media_player.test_player_2", [1])],
)
async def test_media_player_unjoin_group(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    entity_id: str,
    expected_args: list[int],
) -> None:
    """Test ungrouping of media players through the unjoin service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_UNJOIN,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    controller.set_group.assert_called_once_with(expected_args)


async def test_media_player_unjoin_group_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test ungrouping of media players through the unjoin service error raises."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.set_group.side_effect = HeosError("error")
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to unjoin player: error"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_UNJOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
            },
            blocking=True,
        )


async def test_media_player_group_fails_when_entity_removed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test grouping fails when entity removed."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    # Remove one of the players
    entity_registry.async_remove("media_player.test_player_2")

    # Attempt to group
    with pytest.raises(ServiceValidationError, match="was not found"):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_GROUP_MEMBERS: ["media_player.test_player_2"],
            },
            blocking=True,
        )
    controller.set_group.assert_not_called()


async def test_media_player_group_fails_wrong_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test grouping fails when trying to join from the wrong integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    # Create an entity in another integration
    entry = entity_registry.async_get_or_create(
        "media_player", "Other", "test_player_2"
    )

    # Attempt to group
    with pytest.raises(
        ServiceValidationError, match="is not a HEOS media player entity"
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_GROUP_MEMBERS: [entry.entity_id],
            },
            blocking=True,
        )
    controller.set_group.assert_not_called()


async def test_get_queue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    queue: list[QueueItem],
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get queue service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.player_get_queue.return_value = queue
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_QUEUE,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
        },
        blocking=True,
        return_response=True,
    )
    controller.player_get_queue.assert_called_once_with(1, None, None)
    assert response == snapshot


async def test_remove_from_queue(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the get queue service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_FROM_QUEUE,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_QUEUE_IDS: [1, "2"]},
        blocking=True,
    )
    controller.player_remove_from_queue.assert_called_once_with(1, [1, 2])


async def test_move_queue_item_queue(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the move queue service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MOVE_QUEUE_ITEM,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_QUEUE_IDS: [1, "2"],
            ATTR_DESTINATION_POSITION: 10,
        },
        blocking=True,
    )
    controller.player_move_queue_item.assert_called_once_with(1, [1, 2], 10)


async def test_move_queue_item_queue_error_raises(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test move queue raises error when failed."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.player_move_queue_item.side_effect = HeosError("error")
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to move queue item: error"),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MOVE_QUEUE_ITEM,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_QUEUE_IDS: [1, "2"],
                ATTR_DESTINATION_POSITION: 10,
            },
            blocking=True,
        )
