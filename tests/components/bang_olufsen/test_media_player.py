"""Test the Bang & Olufsen media_player entity."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
import logging
from unittest.mock import AsyncMock, Mock, patch

from mozart_api.exceptions import ApiException, NotFoundException
from mozart_api.models import (
    BeolinkLeader,
    BeolinkSelf,
    PlaybackContentMetadata,
    PlayQueueSettings,
    RenderingState,
    Source,
    SourceArray,
    WebsocketNotificationTag,
)
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props
from voluptuous import Invalid, MultipleInvalid

from homeassistant.components.bang_olufsen.const import (
    BANG_OLUFSEN_REPEAT_FROM_HA,
    BANG_OLUFSEN_STATES,
    DOMAIN,
    BangOlufsenSource,
)
from homeassistant.components.media_player import (
    ATTR_GROUP_MEMBERS,
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_JOIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_PLAY_MEDIA,
    SERVICE_REPEAT_SET,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    SERVICE_SHUFFLE_SET,
    SERVICE_TURN_OFF,
    SERVICE_UNJOIN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.setup import async_setup_component

from .const import (
    TEST_ACTIVE_SOUND_MODE_NAME,
    TEST_ACTIVE_SOUND_MODE_NAME_2,
    TEST_AUDIO_SOURCES,
    TEST_DEEZER_FLOW,
    TEST_DEEZER_PLAYLIST,
    TEST_DEEZER_TRACK,
    TEST_FALLBACK_SOURCES,
    TEST_FRIENDLY_NAME_2,
    TEST_JID_1,
    TEST_JID_2,
    TEST_JID_3,
    TEST_JID_4,
    TEST_LISTENING_MODE_REF,
    TEST_MEDIA_PLAYER_ENTITY_ID,
    TEST_MEDIA_PLAYER_ENTITY_ID_2,
    TEST_MEDIA_PLAYER_ENTITY_ID_3,
    TEST_OVERLAY_INVALID_OFFSET_VOLUME_TTS,
    TEST_OVERLAY_OFFSET_VOLUME_TTS,
    TEST_PLAYBACK_ERROR,
    TEST_PLAYBACK_METADATA,
    TEST_PLAYBACK_PROGRESS,
    TEST_PLAYBACK_STATE_PAUSED,
    TEST_PLAYBACK_STATE_PLAYING,
    TEST_PLAYBACK_STATE_TURN_OFF,
    TEST_RADIO_STATION,
    TEST_SEEK_POSITION_HOME_ASSISTANT_FORMAT,
    TEST_SOUND_MODE_2,
    TEST_SOUND_MODES,
    TEST_SOURCE,
    TEST_SOURCES,
    TEST_VIDEO_SOURCES,
    TEST_VOLUME,
    TEST_VOLUME_HOME_ASSISTANT_FORMAT,
    TEST_VOLUME_MUTED,
    TEST_VOLUME_MUTED_HOME_ASSISTANT_FORMAT,
)

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_initialization(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
) -> None:
    """Test the integration is initialized properly in _initialize, async_added_to_hass and __init__."""

    caplog.set_level(logging.DEBUG)

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Ensure that the logger has been called with the debug message
    assert "Connected to: Beosound Balance 11111111 running SW 1.0.0" in caplog.text

    # Check state (The initial state in this test does not contain all that much.
    # States are tested using simulated WebSocket events.)
    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states.attributes[ATTR_INPUT_SOURCE_LIST] == TEST_SOURCES
    assert states.attributes[ATTR_MEDIA_POSITION_UPDATED_AT]
    assert states.attributes[ATTR_SOUND_MODE_LIST] == TEST_SOUND_MODES

    # Check API calls
    mock_mozart_client.get_softwareupdate_status.assert_called_once()
    mock_mozart_client.get_product_state.assert_called_once()
    mock_mozart_client.get_available_sources.assert_called_once()
    mock_mozart_client.get_remote_menu.assert_called_once()
    mock_mozart_client.get_listening_mode_set.assert_called_once()
    mock_mozart_client.get_active_listening_mode.assert_called_once()
    mock_mozart_client.get_beolink_self.assert_called_once()
    mock_mozart_client.get_beolink_peers.assert_called_once()
    mock_mozart_client.get_beolink_listeners.assert_called_once()


async def test_async_update_sources_audio_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
) -> None:
    """Test sources are correctly handled in _async_update_sources."""
    mock_mozart_client.get_remote_menu.return_value = {}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states.attributes[ATTR_INPUT_SOURCE_LIST] == TEST_AUDIO_SOURCES


async def test_async_update_sources_outdated_api(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test fallback sources are correctly handled in _async_update_sources."""
    mock_mozart_client.get_available_sources.side_effect = ValueError()

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert (
        states.attributes[ATTR_INPUT_SOURCE_LIST]
        == TEST_FALLBACK_SOURCES + TEST_VIDEO_SOURCES
    )


async def test_async_update_sources_remote(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _async_update_sources is called when there are new video sources."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    notification_callback = mock_mozart_client.get_notification_notifications.call_args[
        0
    ][0]

    # This is not an ideal check, but I couldn't get anything else to work
    assert mock_mozart_client.get_available_sources.call_count == 1
    assert mock_mozart_client.get_remote_menu.call_count == 1

    # Send the remote menu Websocket event
    notification_callback(WebsocketNotificationTag(value="remoteMenuChanged"))

    assert mock_mozart_client.get_available_sources.call_count == 2
    assert mock_mozart_client.get_remote_menu.call_count == 2


async def test_async_update_sources_availability(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the playback_source WebSocket event updates available playback sources."""
    # Remove video sources to simplify test
    mock_mozart_client.get_remote_menu.return_value = {}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    playback_source_callback = (
        mock_mozart_client.get_playback_source_notifications.call_args[0][0]
    )

    assert mock_mozart_client.get_available_sources.call_count == 1

    # Add a source that is available and playable
    mock_mozart_client.get_available_sources.return_value = SourceArray(
        items=[TEST_SOURCE]
    )

    # Send playback_source. The source is not actually used, so its attributes don't matter
    playback_source_callback(Source())

    assert mock_mozart_client.get_available_sources.call_count == 2
    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states.attributes[ATTR_INPUT_SOURCE_LIST] == [TEST_SOURCE.name]


async def test_async_update_playback_metadata(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _async_update_playback_metadata."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    playback_metadata_callback = (
        mock_mozart_client.get_playback_metadata_notifications.call_args[0][0]
    )

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert ATTR_MEDIA_DURATION not in states.attributes
    assert ATTR_MEDIA_TITLE not in states.attributes
    assert ATTR_MEDIA_ALBUM_NAME not in states.attributes
    assert ATTR_MEDIA_ALBUM_ARTIST not in states.attributes
    assert ATTR_MEDIA_TRACK not in states.attributes
    assert ATTR_MEDIA_CHANNEL not in states.attributes

    # Send the WebSocket event dispatch
    playback_metadata_callback(TEST_PLAYBACK_METADATA)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert (
        states.attributes[ATTR_MEDIA_DURATION]
        == TEST_PLAYBACK_METADATA.total_duration_seconds
    )
    assert states.attributes[ATTR_MEDIA_TITLE] == TEST_PLAYBACK_METADATA.title
    assert states.attributes[ATTR_MEDIA_ALBUM_NAME] == TEST_PLAYBACK_METADATA.album_name
    assert (
        states.attributes[ATTR_MEDIA_ALBUM_ARTIST] == TEST_PLAYBACK_METADATA.artist_name
    )
    assert states.attributes[ATTR_MEDIA_TRACK] == TEST_PLAYBACK_METADATA.track
    assert states.attributes[ATTR_MEDIA_CHANNEL] == TEST_PLAYBACK_METADATA.organization


async def test_async_update_playback_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _async_update_playback_error."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    playback_error_callback = (
        mock_mozart_client.get_playback_error_notifications.call_args[0][0]
    )

    # The async_dispatcher_send function seems to swallow exceptions, making pytest.raises unusable
    playback_error_callback(TEST_PLAYBACK_ERROR)

    assert (
        "Exception in _async_update_playback_error when dispatching '11111111_playback_error': (PlaybackError(error='Test error', item=None),)"
        in caplog.text
    )


async def test_async_update_playback_progress(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _async_update_playback_progress."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    playback_progress_callback = (
        mock_mozart_client.get_playback_progress_notifications.call_args[0][0]
    )

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert ATTR_MEDIA_POSITION not in states.attributes
    old_updated_at = states.attributes[ATTR_MEDIA_POSITION_UPDATED_AT]
    assert old_updated_at

    playback_progress_callback(TEST_PLAYBACK_PROGRESS)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states.attributes[ATTR_MEDIA_POSITION] == TEST_PLAYBACK_PROGRESS.progress
    new_updated_at = states.attributes[ATTR_MEDIA_POSITION_UPDATED_AT]
    assert new_updated_at
    assert old_updated_at != new_updated_at


async def test_async_update_playback_state(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _async_update_playback_state."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    playback_state_callback = (
        mock_mozart_client.get_playback_state_notifications.call_args[0][0]
    )

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states.state == MediaPlayerState.PLAYING

    playback_state_callback(TEST_PLAYBACK_STATE_PAUSED)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states.state == TEST_PLAYBACK_STATE_PAUSED.value


@pytest.mark.parametrize(
    ("source", "content_type", "progress", "metadata"),
    [
        # Normal source, music mediatype expected
        (
            TEST_SOURCE,
            MediaType.MUSIC,
            TEST_PLAYBACK_PROGRESS.progress,
            PlaybackContentMetadata(),
        ),
        # URI source, url media type expected
        (
            BangOlufsenSource.URI_STREAMER,
            MediaType.URL,
            TEST_PLAYBACK_PROGRESS.progress,
            PlaybackContentMetadata(),
        ),
        # Line-In source,media type expected, progress 0 expected
        (
            BangOlufsenSource.LINE_IN,
            MediaType.MUSIC,
            0,
            PlaybackContentMetadata(),
        ),
    ],
)
async def test_async_update_source_change(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    source: Source,
    content_type: MediaType,
    progress: int,
    metadata: PlaybackContentMetadata,
) -> None:
    """Test _async_update_source_change."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    playback_progress_callback = (
        mock_mozart_client.get_playback_progress_notifications.call_args[0][0]
    )
    playback_metadata_callback = (
        mock_mozart_client.get_playback_metadata_notifications.call_args[0][0]
    )
    source_change_callback = (
        mock_mozart_client.get_source_change_notifications.call_args[0][0]
    )

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert ATTR_INPUT_SOURCE not in states.attributes
    assert states.attributes[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC

    # Simulate progress attribute being available
    playback_progress_callback(TEST_PLAYBACK_PROGRESS)

    # Simulate metadata
    playback_metadata_callback(metadata)
    source_change_callback(source)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states.attributes[ATTR_INPUT_SOURCE] == source.name
    assert states.attributes[ATTR_MEDIA_CONTENT_TYPE] == content_type
    assert states.attributes[ATTR_MEDIA_POSITION] == progress


async def test_async_turn_off(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_turn_off."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    playback_state_callback = (
        mock_mozart_client.get_playback_state_notifications.call_args[0][0]
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    playback_state_callback(TEST_PLAYBACK_STATE_TURN_OFF)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert TEST_PLAYBACK_STATE_TURN_OFF.value
    assert states.state == BANG_OLUFSEN_STATES[TEST_PLAYBACK_STATE_TURN_OFF.value]

    # Check API call
    mock_mozart_client.post_standby.assert_called_once()


async def test_async_set_volume_level(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_set_volume_level and _async_update_volume by proxy."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    volume_callback = mock_mozart_client.get_volume_notifications.call_args[0][0]

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert ATTR_MEDIA_VOLUME_LEVEL not in states.attributes

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_VOLUME_LEVEL: TEST_VOLUME_HOME_ASSISTANT_FORMAT,
        },
        blocking=True,
    )

    # The service call will trigger a WebSocket notification
    volume_callback(TEST_VOLUME)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert (
        states.attributes[ATTR_MEDIA_VOLUME_LEVEL] == TEST_VOLUME_HOME_ASSISTANT_FORMAT
    )

    mock_mozart_client.set_current_volume_level.assert_called_once_with(
        volume_level=TEST_VOLUME.level
    )


async def test_async_update_beolink_line_in(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _async_update_beolink with line-in and no active Beolink session."""
    # Ensure no listeners
    mock_mozart_client.get_beolink_listeners.return_value = []

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    source_change_callback = (
        mock_mozart_client.get_source_change_notifications.call_args[0][0]
    )
    beolink_callback = mock_mozart_client.get_notification_notifications.call_args[0][0]

    # Set source
    source_change_callback(BangOlufsenSource.LINE_IN)
    beolink_callback(WebsocketNotificationTag(value="beolinkListeners"))

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states.attributes["group_members"] == []

    # Called once during _initialize and once during _async_update_beolink
    assert mock_mozart_client.get_beolink_listeners.call_count == 2
    assert mock_mozart_client.get_beolink_peers.call_count == 2


async def test_async_update_beolink_listener(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_config_entry_core: MockConfigEntry,
) -> None:
    """Test _async_update_beolink as a listener."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    playback_metadata_callback = (
        mock_mozart_client.get_playback_metadata_notifications.call_args[0][0]
    )

    # Add another entity
    mock_config_entry_core.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_core.entry_id)

    # Runs _async_update_beolink
    playback_metadata_callback(
        PlaybackContentMetadata(
            remote_leader=BeolinkLeader(
                friendly_name=TEST_FRIENDLY_NAME_2, jid=TEST_JID_2
            )
        )
    )

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states.attributes["group_members"] == [
        TEST_MEDIA_PLAYER_ENTITY_ID_2,
        TEST_MEDIA_PLAYER_ENTITY_ID,
    ]

    # Called once for each entity during _initialize
    assert mock_mozart_client.get_beolink_listeners.call_count == 2
    # Called once for each entity during _initialize and
    # once more during _async_update_beolink for the entity that has the callback associated with it.
    assert mock_mozart_client.get_beolink_peers.call_count == 3

    # Main entity
    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states == snapshot(exclude=props("media_position_updated_at"))

    # Secondary entity
    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID_2))
    assert states == snapshot(exclude=props("media_position_updated_at"))


async def test_async_update_name_and_beolink(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _async_update_name_and_beolink."""
    # Change response to ensure device name is changed
    mock_mozart_client.get_beolink_self.return_value = BeolinkSelf(
        friendly_name=TEST_FRIENDLY_NAME_2, jid=TEST_JID_1
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    configuration_callback = (
        mock_mozart_client.get_notification_notifications.call_args[0][0]
    )
    # Trigger callback
    configuration_callback(WebsocketNotificationTag(value="configuration"))

    await hass.async_block_till_done()

    assert mock_mozart_client.get_beolink_self.call_count == 2
    assert mock_mozart_client.get_beolink_peers.call_count == 2
    assert mock_mozart_client.get_beolink_listeners.call_count == 2

    # Check that device name has been changed
    assert mock_config_entry.unique_id
    assert (
        device := device_registry.async_get_device(
            identifiers={(DOMAIN, mock_config_entry.unique_id)}
        )
    )
    assert device.name == TEST_FRIENDLY_NAME_2


async def test_async_mute_volume(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_mute_volume."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    volume_callback = mock_mozart_client.get_volume_notifications.call_args[0][0]

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert ATTR_MEDIA_VOLUME_MUTED not in states.attributes

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_VOLUME_MUTED: TEST_VOLUME_HOME_ASSISTANT_FORMAT,
        },
        blocking=True,
    )

    # The service call will trigger a WebSocket notification
    volume_callback(TEST_VOLUME_MUTED)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert (
        states.attributes[ATTR_MEDIA_VOLUME_MUTED]
        == TEST_VOLUME_MUTED_HOME_ASSISTANT_FORMAT
    )

    mock_mozart_client.set_volume_mute.assert_called_once_with(
        volume_mute=TEST_VOLUME_MUTED.muted
    )


@pytest.mark.parametrize(
    ("initial_state", "command"),
    [
        # Current state is playing, "pause" command expected
        (TEST_PLAYBACK_STATE_PLAYING, "pause"),
        # Current state is paused, "play" command expected
        (TEST_PLAYBACK_STATE_PAUSED, "play"),
    ],
)
async def test_async_media_play_pause(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    initial_state: RenderingState,
    command: str,
) -> None:
    """Test async_media_play_pause."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    playback_state_callback = (
        mock_mozart_client.get_playback_state_notifications.call_args[0][0]
    )

    # Set the initial state
    playback_state_callback(initial_state)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert initial_state.value
    assert states.state == BANG_OLUFSEN_STATES[initial_state.value]

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY_PAUSE,
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    mock_mozart_client.post_playback_command.assert_called_once_with(command=command)


async def test_async_media_stop(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_media_stop."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    playback_state_callback = (
        mock_mozart_client.get_playback_state_notifications.call_args[0][0]
    )

    # Set the state to playing
    playback_state_callback(TEST_PLAYBACK_STATE_PLAYING)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert TEST_PLAYBACK_STATE_PLAYING.value
    assert states.state == BANG_OLUFSEN_STATES[TEST_PLAYBACK_STATE_PLAYING.value]

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    # Check API call
    mock_mozart_client.post_playback_command.assert_called_once_with(command="stop")


async def test_async_media_next_track(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_media_next_track."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_NEXT_TRACK,
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    mock_mozart_client.post_playback_command.assert_called_once_with(command="skip")


@pytest.mark.parametrize(
    ("source", "expected_result", "seek_called_times"),
    [
        # Seekable source, seek expected
        (TEST_SOURCE, does_not_raise(), 1),
        # Non seekable source, seek shouldn't work
        (BangOlufsenSource.LINE_IN, pytest.raises(HomeAssistantError), 0),
        # Malformed source, seek shouldn't work
        (Source(), pytest.raises(HomeAssistantError), 0),
    ],
)
async def test_async_media_seek(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    source: Source,
    expected_result: AbstractContextManager,
    seek_called_times: int,
) -> None:
    """Test async_media_seek."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    source_change_callback = (
        mock_mozart_client.get_source_change_notifications.call_args[0][0]
    )

    # Set the source
    source_change_callback(source)

    # Check results
    with expected_result:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_SEEK,
            {
                ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
                ATTR_MEDIA_SEEK_POSITION: TEST_SEEK_POSITION_HOME_ASSISTANT_FORMAT,
            },
            blocking=True,
        )

    assert mock_mozart_client.seek_to_position.call_count == seek_called_times


async def test_async_media_previous_track(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_media_previous_track."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    mock_mozart_client.post_playback_command.assert_called_once_with(command="prev")


async def test_async_clear_playlist(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_clear_playlist."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_CLEAR_PLAYLIST,
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    mock_mozart_client.post_clear_queue.assert_called_once()


@pytest.mark.parametrize(
    ("source", "expected_result", "audio_source_call", "video_source_call"),
    [
        # Invalid source
        ("Test source", pytest.raises(ServiceValidationError), 0, 0),
        # Valid audio source
        (TEST_SOURCE.name, does_not_raise(), 1, 0),
        # Valid video source
        (TEST_VIDEO_SOURCES[0], does_not_raise(), 0, 1),
    ],
)
async def test_async_select_source(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    source: str,
    expected_result: AbstractContextManager,
    audio_source_call: int,
    video_source_call: int,
) -> None:
    """Test async_select_source with an invalid source."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    with expected_result:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {
                ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
                ATTR_INPUT_SOURCE: source,
            },
            blocking=True,
        )

    assert mock_mozart_client.set_active_source.call_count == audio_source_call
    assert mock_mozart_client.post_remote_trigger.call_count == video_source_call


async def test_async_select_sound_mode(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_select_sound_mode."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states.attributes[ATTR_SOUND_MODE] == TEST_ACTIVE_SOUND_MODE_NAME

    active_listening_mode_callback = (
        mock_mozart_client.get_active_listening_mode_notifications.call_args[0][0]
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_SOUND_MODE: TEST_ACTIVE_SOUND_MODE_NAME_2,
        },
        blocking=True,
    )

    active_listening_mode_callback(TEST_LISTENING_MODE_REF)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states.attributes[ATTR_SOUND_MODE] == TEST_ACTIVE_SOUND_MODE_NAME_2

    mock_mozart_client.activate_listening_mode.assert_called_once_with(
        id=TEST_SOUND_MODE_2
    )


async def test_async_select_sound_mode_invalid(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_select_sound_mode with an invalid sound_mode."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOUND_MODE,
            {
                ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
                ATTR_SOUND_MODE: "invalid_sound_mode",
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_sound_mode"
    assert exc_info.errisinstance(ServiceValidationError)


async def test_async_play_media_invalid_type(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_play_media only accepts valid media types."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
                ATTR_MEDIA_CONTENT_ID: "test",
                ATTR_MEDIA_CONTENT_TYPE: "invalid type",
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_media_type"
    assert exc_info.errisinstance(HomeAssistantError)


async def test_async_play_media_url(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_play_media URL."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Setup media source
    await async_setup_component(hass, "media_source", {"media_source": {}})

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/doorbell.mp3",
            ATTR_MEDIA_CONTENT_TYPE: "audio/mpeg",
        },
        blocking=True,
    )

    mock_mozart_client.post_uri_source.assert_called_once()


async def test_async_play_media_overlay_absolute_volume_uri(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_play_media overlay with Home Assistant local URI and absolute volume."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await async_setup_component(hass, "media_source", {"media_source": {}})

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/doorbell.mp3",
            ATTR_MEDIA_CONTENT_TYPE: "music",
            ATTR_MEDIA_ANNOUNCE: True,
            ATTR_MEDIA_EXTRA: {"overlay_absolute_volume": 60},
        },
        blocking=True,
    )

    mock_mozart_client.post_overlay_play.assert_called_once()

    # Check that the API call was as expected
    args, _ = mock_mozart_client.post_overlay_play.call_args
    assert args[0].volume_absolute == 60
    assert "/local/doorbell.mp3" in args[0].uri.location


async def test_async_play_media_overlay_invalid_offset_volume_tts(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_play_media with Home Assistant invalid offset volume and B&O tts."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "Dette er en test",
            ATTR_MEDIA_CONTENT_TYPE: "overlay_tts",
            ATTR_MEDIA_ANNOUNCE: True,
            ATTR_MEDIA_EXTRA: {
                "overlay_offset_volume": 20,
                "overlay_tts_language": "da-dk",
            },
        },
        blocking=True,
    )
    assert "Error setting volume" in caplog.text

    mock_mozart_client.post_overlay_play.assert_called_once_with(
        TEST_OVERLAY_INVALID_OFFSET_VOLUME_TTS
    )


async def test_async_play_media_overlay_offset_volume_tts(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_play_media with Home Assistant invalid offset volume and B&O tts."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    volume_callback = mock_mozart_client.get_volume_notifications.call_args[0][0]

    # Set the volume to enable offset
    volume_callback(TEST_VOLUME)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "This is a test",
            ATTR_MEDIA_CONTENT_TYPE: "overlay_tts",
            ATTR_MEDIA_ANNOUNCE: True,
            ATTR_MEDIA_EXTRA: {"overlay_offset_volume": 20},
        },
        blocking=True,
    )

    mock_mozart_client.post_overlay_play.assert_called_once_with(
        TEST_OVERLAY_OFFSET_VOLUME_TTS
    )


async def test_async_play_media_tts(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_play_media with Home Assistant tts."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await async_setup_component(hass, "media_source", {"media_source": {}})

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/doorbell.mp3",
            ATTR_MEDIA_CONTENT_TYPE: "provider",
        },
        blocking=True,
    )

    mock_mozart_client.post_overlay_play.assert_called_once()


async def test_async_play_media_radio(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_play_media with B&O radio."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "1234567890123456",
            ATTR_MEDIA_CONTENT_TYPE: "radio",
        },
        blocking=True,
    )

    mock_mozart_client.run_provided_scene.assert_called_once_with(
        scene_properties=TEST_RADIO_STATION
    )


async def test_async_play_media_favourite(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_play_media with B&O favourite."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "1",
            ATTR_MEDIA_CONTENT_TYPE: "favourite",
        },
        blocking=True,
    )

    mock_mozart_client.activate_preset.assert_called_once_with(id=int("1"))


async def test_async_play_media_deezer_flow(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_play_media with Deezer flow."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "flow",
            ATTR_MEDIA_CONTENT_TYPE: "deezer",
            ATTR_MEDIA_EXTRA: {"id": "123"},
        },
        blocking=True,
    )

    mock_mozart_client.start_deezer_flow.assert_called_once_with(
        user_flow=TEST_DEEZER_FLOW
    )


async def test_async_play_media_deezer_playlist(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_play_media with Deezer playlist."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "playlist:1234567890",
            ATTR_MEDIA_CONTENT_TYPE: "deezer",
            ATTR_MEDIA_EXTRA: {"start_from": 123},
        },
        blocking=True,
    )

    mock_mozart_client.add_to_queue.assert_called_once_with(
        play_queue_item=TEST_DEEZER_PLAYLIST
    )


async def test_async_play_media_deezer_track(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_play_media with Deezer track."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "1234567890",
            ATTR_MEDIA_CONTENT_TYPE: "deezer",
        },
        blocking=True,
    )

    mock_mozart_client.add_to_queue.assert_called_once_with(
        play_queue_item=TEST_DEEZER_TRACK
    )


async def test_async_play_media_invalid_deezer(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_play_media with an invalid/no Deezer login."""

    # codespell can't see the escaped ', so it thinks the word is misspelled
    mock_mozart_client.start_deezer_flow.side_effect = ApiException(
        status=400,
        reason="Bad Request",
        http_resp=Mock(
            status=400,
            reason="Bad Request",
            data='{"message": "Couldn\'t start user flow for me"}',  # codespell:ignore
        ),
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
                ATTR_MEDIA_CONTENT_ID: "flow",
                ATTR_MEDIA_CONTENT_TYPE: "deezer",
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "play_media_error"
    assert exc_info.errisinstance(HomeAssistantError)

    mock_mozart_client.start_deezer_flow.assert_called_once()


async def test_async_play_media_url_m3u(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_play_media URL with the m3u extension."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await async_setup_component(hass, "media_source", {"media_source": {}})

    with (
        pytest.raises(HomeAssistantError) as exc_info,
        patch(
            "homeassistant.components.bang_olufsen.media_player.async_process_play_media_url",
            return_value="https://test.com/test.m3u",
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
                ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/doorbell.mp3",
                ATTR_MEDIA_CONTENT_TYPE: "audio/mpeg",
            },
            blocking=True,
        )

    # Check exception
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "m3u_invalid_format"
    assert exc_info.errisinstance(HomeAssistantError)

    mock_mozart_client.post_uri_source.assert_not_called()


@pytest.mark.parametrize(
    ("child", "present"),
    [
        # Audio source expected
        (
            {
                "title": "test.mp3",
                "media_class": "music",
                "media_content_type": "audio/mpeg",
                "media_content_id": "media-source://media_source/local/test.mp3",
                "can_play": True,
                "can_expand": False,
                "can_search": False,
                "thumbnail": None,
                "children_media_class": None,
            },
            True,
        ),
        # Video source not expected
        (
            {
                "title": "test.mp4",
                "media_class": "video",
                "media_content_type": "video/mp4",
                "media_content_id": ("media-source://media_source/local/test.mp4"),
                "can_play": True,
                "can_expand": False,
                "can_search": False,
                "thumbnail": None,
                "children_media_class": None,
            },
            False,
        ),
    ],
)
async def test_async_browse_media(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    child: dict[str, str | bool | None],
    present: bool,
) -> None:
    """Test async_browse_media with audio and video source."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await async_setup_component(hass, "media_source", {"media_source": {}})

    client = await hass_ws_client()
    await client.send_json_auto_id(
        {
            "type": "media_player/browse_media",
            "entity_id": TEST_MEDIA_PLAYER_ENTITY_ID,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    assert (child in response["result"]["children"]) is present


@pytest.mark.parametrize(
    ("group_members", "expand_count", "join_count"),
    [
        # Valid member
        ([TEST_MEDIA_PLAYER_ENTITY_ID_2], 1, 0),
        # Touch to join
        ([], 0, 1),
    ],
)
async def test_async_join_players(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_config_entry_core: MockConfigEntry,
    group_members: list[str],
    expand_count: int,
    join_count: int,
) -> None:
    """Test async_join_players."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    source_change_callback = (
        mock_mozart_client.get_source_change_notifications.call_args[0][0]
    )

    # Add another entity
    mock_config_entry_core.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_core.entry_id)

    # Set the source to a beolink expandable source
    source_change_callback(TEST_SOURCE)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_JOIN,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_GROUP_MEMBERS: group_members,
        },
        blocking=True,
    )

    assert mock_mozart_client.post_beolink_expand.call_count == expand_count
    assert mock_mozart_client.join_latest_beolink_experience.call_count == join_count

    # Main entity
    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states == snapshot(exclude=props("media_position_updated_at"))

    # Secondary entity
    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID_2))
    assert states == snapshot(exclude=props("media_position_updated_at"))


@pytest.mark.parametrize(
    ("source", "group_members", "expected_result", "error_type"),
    [
        # Invalid source
        (
            BangOlufsenSource.LINE_IN,
            [TEST_MEDIA_PLAYER_ENTITY_ID_2],
            pytest.raises(ServiceValidationError),
            "invalid_source",
        ),
        # Invalid media_player entity
        (
            TEST_SOURCE,
            [TEST_MEDIA_PLAYER_ENTITY_ID_3],
            pytest.raises(ServiceValidationError),
            "invalid_grouping_entity",
        ),
    ],
)
async def test_async_join_players_invalid(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_config_entry_core: MockConfigEntry,
    source: Source,
    group_members: list[str],
    expected_result: AbstractContextManager,
    error_type: str,
) -> None:
    """Test async_join_players with an invalid media_player entity."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    source_change_callback = (
        mock_mozart_client.get_source_change_notifications.call_args[0][0]
    )

    mock_config_entry_core.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_core.entry_id)

    source_change_callback(source)

    with expected_result as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
                ATTR_GROUP_MEMBERS: group_members,
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == error_type
    assert exc_info.errisinstance(HomeAssistantError)

    assert mock_mozart_client.post_beolink_expand.call_count == 0
    assert mock_mozart_client.join_latest_beolink_experience.call_count == 0

    # Main entity
    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states == snapshot(exclude=props("media_position_updated_at"))

    # Secondary entity
    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID_2))
    assert states == snapshot(exclude=props("media_position_updated_at"))


async def test_async_unjoin_player(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_unjoin_player."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_UNJOIN,
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    mock_mozart_client.post_beolink_leave.assert_called_once()

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states == snapshot(exclude=props("media_position_updated_at"))


@pytest.mark.parametrize(
    (
        "service_parameters",
        "method_parameters",
    ),
    [
        # Defined JID
        (
            {"beolink_jid": TEST_JID_2},
            {"jid": TEST_JID_2},
        ),
        # Defined JID and source
        (
            {"beolink_jid": TEST_JID_2, "source_id": TEST_SOURCE.id},
            {"jid": TEST_JID_2, "source": TEST_SOURCE.id},
        ),
        # Defined JID and Beolink Converter NL/ML source
        (
            {"beolink_jid": TEST_JID_2, "source_id": "cd"},
            {"jid": TEST_JID_2, "source": "CD"},
        ),
    ],
)
async def test_async_beolink_join(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service_parameters: dict[str, str],
    method_parameters: dict[str, str],
) -> None:
    """Test async_beolink_join with defined JID and JID and source."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        DOMAIN,
        "beolink_join",
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID, **service_parameters},
        blocking=True,
    )

    mock_mozart_client.join_beolink_peer.assert_called_once_with(**method_parameters)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states == snapshot(exclude=props("media_position_updated_at"))


@pytest.mark.parametrize(
    (
        "service_parameters",
        "expected_result",
    ),
    [
        # Defined invalid JID
        (
            {"beolink_jid": "not_a_jid"},
            pytest.raises(Invalid),
        ),
        # Defined invalid source
        (
            {"source_id": "invalid_source"},
            pytest.raises(MultipleInvalid),
        ),
        # Defined invalid JID and invalid source
        (
            {"beolink_jid": "not_a_jid", "source_id": "invalid_source"},
            pytest.raises(MultipleInvalid),
        ),
    ],
)
async def test_async_beolink_join_invalid(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service_parameters: dict[str, str],
    expected_result: AbstractContextManager,
) -> None:
    """Test invalid async_beolink_join calls with defined JID or source ID."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    with expected_result:
        await hass.services.async_call(
            DOMAIN,
            "beolink_join",
            {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID, **service_parameters},
            blocking=True,
        )

    mock_mozart_client.join_beolink_peer.assert_not_called()

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states == snapshot(exclude=props("media_position_updated_at"))


@pytest.mark.parametrize(
    (
        "parameter",
        "parameter_value",
        "expand_side_effect",
        "log_messages",
        "peers_call_count",
    ),
    [
        # All discovered
        # Valid peers
        ("all_discovered", True, None, [], 2),
        # Invalid peers
        (
            "all_discovered",
            True,
            NotFoundException(),
            [f"Unable to expand to {TEST_JID_3}", f"Unable to expand to {TEST_JID_4}"],
            2,
        ),
        # Beolink JIDs
        # Valid peer
        ("beolink_jids", [TEST_JID_3, TEST_JID_4], None, [], 1),
        # Invalid peer
        (
            "beolink_jids",
            [TEST_JID_3, TEST_JID_4],
            NotFoundException(),
            [
                f"Unable to expand to {TEST_JID_3}. Is the device available on the network?",
                f"Unable to expand to {TEST_JID_4}. Is the device available on the network?",
            ],
            1,
        ),
    ],
)
async def test_async_beolink_expand(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    snapshot: SnapshotAssertion,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    parameter: str,
    parameter_value: bool | list[str],
    expand_side_effect: NotFoundException | None,
    log_messages: list[str],
    peers_call_count: int,
) -> None:
    """Test async_beolink_expand."""
    mock_mozart_client.post_beolink_expand.side_effect = expand_side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    source_change_callback = (
        mock_mozart_client.get_source_change_notifications.call_args[0][0]
    )

    # Set the source to a beolink expandable source
    source_change_callback(TEST_SOURCE)

    await hass.services.async_call(
        DOMAIN,
        "beolink_expand",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            parameter: parameter_value,
        },
        blocking=True,
    )

    # Check log messages
    for log_message in log_messages:
        assert log_message in caplog.text

    # Called once during _initialize and once during async_beolink_expand for all_discovered
    assert mock_mozart_client.get_beolink_peers.call_count == peers_call_count

    assert mock_mozart_client.post_beolink_expand.call_count == len(
        await mock_mozart_client.get_beolink_peers()
    )

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states == snapshot(exclude=props("media_position_updated_at"))


async def test_async_beolink_unexpand(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test test_async_beolink_unexpand."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        DOMAIN,
        "beolink_unexpand",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            "beolink_jids": [TEST_JID_3, TEST_JID_4],
        },
        blocking=True,
    )

    assert mock_mozart_client.post_beolink_unexpand.call_count == 2

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states == snapshot(exclude=props("media_position_updated_at"))


async def test_async_beolink_allstandby(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_beolink_allstandby."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        DOMAIN,
        "beolink_allstandby",
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    mock_mozart_client.post_beolink_allstandby.assert_called_once()

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states == snapshot(exclude=props("media_position_updated_at"))


@pytest.mark.parametrize(
    ("repeat"),
    [
        # Repeat all
        (RepeatMode.ALL),
        # Repeat track
        (RepeatMode.ONE),
        # Repeat none
        (RepeatMode.OFF),
    ],
)
async def test_async_set_repeat(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    repeat: RepeatMode,
) -> None:
    """Test async_set_repeat."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert ATTR_MEDIA_REPEAT not in states.attributes

    # Set the return value of the repeat endpoint to match service call
    mock_mozart_client.get_settings_queue.return_value = PlayQueueSettings(
        repeat=BANG_OLUFSEN_REPEAT_FROM_HA[repeat]
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_REPEAT: repeat,
        },
        blocking=True,
    )
    mock_mozart_client.set_settings_queue.assert_called_once_with(
        play_queue_settings=PlayQueueSettings(
            repeat=BANG_OLUFSEN_REPEAT_FROM_HA[repeat]
        )
    )

    # Test the BANG_OLUFSEN_REPEAT_TO_HA dict by checking property value
    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states.attributes[ATTR_MEDIA_REPEAT] == repeat


@pytest.mark.parametrize(
    ("shuffle"),
    [
        # Shuffle on
        (True),
        # Shuffle off
        (False),
    ],
)
async def test_async_set_shuffle(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    shuffle: bool,
) -> None:
    """Test async_set_shuffle."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert ATTR_MEDIA_SHUFFLE not in states.attributes

    # Set the return value of the shuffle endpoint to match service call
    mock_mozart_client.get_settings_queue.return_value = PlayQueueSettings(
        shuffle=shuffle
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SHUFFLE_SET,
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_SHUFFLE: shuffle,
        },
        blocking=True,
    )
    mock_mozart_client.set_settings_queue.assert_called_once_with(
        play_queue_settings=PlayQueueSettings(shuffle=shuffle)
    )

    assert (states := hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID))
    assert states.attributes[ATTR_MEDIA_SHUFFLE] == shuffle
