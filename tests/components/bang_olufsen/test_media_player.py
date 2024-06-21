"""Test the Bang & Olufsen media_player entity."""

from unittest.mock import patch

from mozart_api.exceptions import ApiException

from homeassistant.components.bang_olufsen.const import (
    BANG_OLUFSEN_STATES,
    WebsocketNotification,
)
from homeassistant.components.media_player.const import (
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
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

from .const import (
    TEST_AUDIO_SOURCES,
    TEST_DEEZER_FLOW,
    TEST_DEEZER_PLAYLIST,
    TEST_DEEZER_TRACK,
    TEST_FALLBACK_SOURCES,
    TEST_MEDIA_PLAYER_ENTITY_ID,
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
    TEST_SERIAL_NUMBER,
    TEST_SOURCE_CHANGE,
    TEST_SOURCE_CHANGE_DEEZER,
    TEST_SOURCES,
    TEST_VIDEO_SOURCES,
    TEST_VOLUME,
    TEST_VOLUME_HOME_ASSISTANT_FORMAT,
    TEST_VOLUME_MUTED,
    TEST_VOLUME_MUTED_HOME_ASSISTANT_FORMAT,
)

from tests.common import MockConfigEntry


async def test_initialization(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_mozart_client
) -> None:
    """Test the integration is initialized properly in _initialize, async_added_to_hass and __init__."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert states.attributes[ATTR_INPUT_SOURCE_LIST] == TEST_SOURCES

    # Check API calls
    mock_mozart_client.get_softwareupdate_status.assert_called_once()
    mock_mozart_client.get_product_state.assert_called_once()
    mock_mozart_client.get_available_sources.assert_called_once()
    mock_mozart_client.get_remote_menu.assert_called_once()


async def test_async_update_sources_audio_only(
    hass: HomeAssistant, mock_config_entry, mock_mozart_client
) -> None:
    """Test sources are correctly handled in _async_update_sources."""
    mock_mozart_client.get_remote_menu.return_value = {}

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert states.attributes[ATTR_INPUT_SOURCE_LIST] == TEST_AUDIO_SOURCES


async def test_async_update_sources_outdated_api(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test fallback sources are correctly handled in _async_update_sources."""
    mock_mozart_client.get_available_sources.side_effect = ValueError()

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Get state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    # Check sources
    assert (
        states.attributes[ATTR_INPUT_SOURCE_LIST]
        == TEST_FALLBACK_SOURCES + TEST_VIDEO_SOURCES
    )


async def test_async_update_playback_metadata(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test _async_update_playback_metadata."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check states
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)

    assert ATTR_MEDIA_DURATION not in states.attributes
    assert ATTR_MEDIA_TITLE not in states.attributes
    assert ATTR_MEDIA_ALBUM_NAME not in states.attributes
    assert ATTR_MEDIA_ALBUM_ARTIST not in states.attributes
    assert ATTR_MEDIA_TRACK not in states.attributes
    assert ATTR_MEDIA_CHANNEL not in states.attributes

    # Send the dispatch
    async_dispatcher_send(
        hass,
        f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.PLAYBACK_METADATA}",
        TEST_PLAYBACK_METADATA,
    )
    # Check new state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)

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
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test _async_update_playback_error."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send the dispatch
    with patch(
        "homeassistant.components.bang_olufsen.media_player._LOGGER.error"
    ) as mock_logger:
        async_dispatcher_send(
            hass,
            f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.PLAYBACK_ERROR}",
            TEST_PLAYBACK_ERROR,
        )
        # Ensure that the logger has been called with the error message
        mock_logger.assert_called_once_with(TEST_PLAYBACK_ERROR.error)


async def test_async_update_playback_progress(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test _async_update_playback_progress."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert ATTR_MEDIA_POSITION not in states.attributes

    # Send the dispatch
    async_dispatcher_send(
        hass,
        f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.PLAYBACK_PROGRESS}",
        TEST_PLAYBACK_PROGRESS,
    )

    # Check new state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert states.attributes[ATTR_MEDIA_POSITION] == TEST_PLAYBACK_PROGRESS.progress


async def test_async_update_playback_state(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test _async_update_playback_state."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert states.state == MediaPlayerState.PLAYING

    # Send the dispatch
    async_dispatcher_send(
        hass,
        f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.PLAYBACK_STATE}",
        TEST_PLAYBACK_STATE_PAUSED,
    )

    # Check new state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert states.state == TEST_PLAYBACK_STATE_PAUSED.value


async def test_async_update_source_change(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test _async_update_source_change."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert ATTR_INPUT_SOURCE not in states.attributes

    # Send the dispatch
    async_dispatcher_send(
        hass,
        f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.SOURCE_CHANGE}",
        TEST_SOURCE_CHANGE,
    )

    # Check new state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert states.attributes[ATTR_INPUT_SOURCE] == TEST_SOURCE_CHANGE.name


async def test_async_turn_off(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_turn_off."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "turn_off",
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
    )

    # The service call will trigger a WebSocket notification
    async_dispatcher_send(
        hass,
        f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.PLAYBACK_STATE}",
        TEST_PLAYBACK_STATE_TURN_OFF,
    )

    # Check state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert states.state == BANG_OLUFSEN_STATES[TEST_PLAYBACK_STATE_TURN_OFF.value]

    # Check API call
    mock_mozart_client.post_standby.assert_called_once()


async def test_async_set_volume_level(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_set_volume_level and _async_update_volume by proxy."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert ATTR_MEDIA_VOLUME_LEVEL not in states.attributes

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "volume_set",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_VOLUME_LEVEL: TEST_VOLUME_HOME_ASSISTANT_FORMAT,
        },
    )

    # The service call will trigger a WebSocket notification
    async_dispatcher_send(
        hass,
        f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.VOLUME}",
        TEST_VOLUME,
    )

    # Check new state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert (
        states.attributes[ATTR_MEDIA_VOLUME_LEVEL] == TEST_VOLUME_HOME_ASSISTANT_FORMAT
    )

    # Check API call
    mock_mozart_client.set_current_volume_level.assert_called_once_with(
        volume_level=TEST_VOLUME.level
    )


async def test_async_mute_volume(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_mute_volume."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert ATTR_MEDIA_VOLUME_MUTED not in states.attributes

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "volume_mute",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_VOLUME_MUTED: TEST_VOLUME_HOME_ASSISTANT_FORMAT,
        },
    )

    # The service call will trigger a WebSocket notification
    async_dispatcher_send(
        hass,
        f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.VOLUME}",
        TEST_VOLUME_MUTED,
    )

    # Check new state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert (
        states.attributes[ATTR_MEDIA_VOLUME_MUTED]
        == TEST_VOLUME_MUTED_HOME_ASSISTANT_FORMAT
    )

    # Check API call
    mock_mozart_client.set_volume_mute.assert_called_once_with(
        volume_mute=TEST_VOLUME_MUTED.muted
    )


async def test_async_media_play_pause_pause(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_media_play_pause pausing."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Set the state to playing
    async_dispatcher_send(
        hass,
        f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.PLAYBACK_STATE}",
        TEST_PLAYBACK_STATE_PLAYING,
    )

    # Check state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert states.state == BANG_OLUFSEN_STATES[TEST_PLAYBACK_STATE_PLAYING.value]

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "media_play_pause",
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
    )

    # Check API call
    mock_mozart_client.post_playback_command.assert_called_once_with(command="pause")


async def test_async_media_play_pause_play(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_media_play_pause playing."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Set the state to paused
    async_dispatcher_send(
        hass,
        f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.PLAYBACK_STATE}",
        TEST_PLAYBACK_STATE_PAUSED,
    )

    # Check state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert states.state == BANG_OLUFSEN_STATES[TEST_PLAYBACK_STATE_PAUSED.value]

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "media_play_pause",
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
    )

    # Check API call
    mock_mozart_client.post_playback_command.assert_called_once_with(command="play")


async def test_async_media_stop(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_media_stop."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Set the state to playing
    async_dispatcher_send(
        hass,
        f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.PLAYBACK_STATE}",
        TEST_PLAYBACK_STATE_PLAYING,
    )

    # Check state
    states = hass.states.get(TEST_MEDIA_PLAYER_ENTITY_ID)
    assert states.state == BANG_OLUFSEN_STATES[TEST_PLAYBACK_STATE_PLAYING.value]

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "media_stop",
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
    )

    # Check API call
    mock_mozart_client.post_playback_command.assert_called_once_with(command="stop")


async def test_async_media_next_track(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_media_next_track."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "media_next_track",
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
    )

    # Check API call
    mock_mozart_client.post_playback_command.assert_called_once_with(command="skip")


async def test_async_media_seek_not_deezer(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_media_seek for a source other than Deezer."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Set the source to a Tidal Connect
    async_dispatcher_send(
        hass,
        f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.SOURCE_CHANGE}",
        TEST_SOURCE_CHANGE,
    )

    # Send a service call
    with patch(
        "homeassistant.components.bang_olufsen.media_player._LOGGER.error"
    ) as mock_logger:
        await hass.services.async_call(
            "media_player",
            "media_seek",
            {
                ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
                ATTR_MEDIA_SEEK_POSITION: TEST_SEEK_POSITION_HOME_ASSISTANT_FORMAT,
            },
        )
        # Ensure that the logger has been called with the error message
        mock_logger.assert_called_once_with(
            "Seeking is currently only supported when using Deezer"
        )

    # Check API call
    mock_mozart_client.seek_to_position.assert_not_called()


async def test_async_media_seek_deezer(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_media_seek for Deezer as source."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Set the source to a Deezer
    async_dispatcher_send(
        hass,
        f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.SOURCE_CHANGE}",
        TEST_SOURCE_CHANGE_DEEZER,
    )

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "media_seek",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_SEEK_POSITION: TEST_SEEK_POSITION_HOME_ASSISTANT_FORMAT,
        },
    )

    # Check API call
    mock_mozart_client.seek_to_position.assert_called_once_with(position_ms=10000)


async def test_async_media_previous_track(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_media_previous_track."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "media_previous_track",
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
    )

    # Check API call
    mock_mozart_client.post_playback_command.assert_called_once_with(command="prev")


async def test_async_clear_playlist(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_clear_playlist."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "clear_playlist",
        {ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID},
    )

    # Check API call
    mock_mozart_client.post_clear_queue.assert_called_once()


async def test_async_select_source_invalid(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_select_source with an invalid source."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    with patch(
        "homeassistant.components.bang_olufsen.media_player._LOGGER.error"
    ) as mock_logger:
        await hass.services.async_call(
            "media_player",
            "select_source",
            {
                ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
                ATTR_INPUT_SOURCE: TEST_SOURCE_CHANGE_DEEZER.name,
            },
        )
        # Ensure that the logger has been called with the error message
        mock_logger.assert_called_once()

    # Check API call
    mock_mozart_client.set_active_source.assert_not_called()
    mock_mozart_client.post_remote_trigger.assert_not_called()


async def test_async_select_source_audio(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_select_source with a valid audio source."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "select_source",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_INPUT_SOURCE: TEST_SOURCE_CHANGE.name,
        },
    )

    # Check API call
    mock_mozart_client.set_active_source.assert_called_once_with(TEST_SOURCE_CHANGE.id)
    mock_mozart_client.post_remote_trigger.assert_not_called()


async def test_async_select_source_video(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_select_source with a valid video source."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "select_source",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_INPUT_SOURCE: TEST_VIDEO_SOURCES[0],
        },
    )

    # Check API call
    mock_mozart_client.set_active_source.assert_not_called()
    mock_mozart_client.post_remote_trigger.assert_called_once()


async def test_async_play_media_invalid_type(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_play_media only accepts valid media types."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    with patch(
        "homeassistant.components.bang_olufsen.media_player._LOGGER.error"
    ) as mock_logger:
        # Send a service call
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
                ATTR_MEDIA_CONTENT_ID: "test",
                ATTR_MEDIA_CONTENT_TYPE: "invalid type",
            },
        )

        # Ensure that the logger has been called with the error message
        mock_logger.assert_called_once()


async def test_async_play_media_url(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_play_media URL."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Setup media source
    await async_setup_component(hass, "media_source", {"media_source": {}})

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/doorbell.mp3",
            ATTR_MEDIA_CONTENT_TYPE: "audio/mpeg",
        },
    )

    # Check API call
    mock_mozart_client.post_uri_source.assert_called_once()


async def test_async_play_media_overlay_absolute_volume_uri(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_play_media overlay with Home Assistant local URI and absolute volume."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Setup media source
    await async_setup_component(hass, "media_source", {"media_source": {}})

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/doorbell.mp3",
            ATTR_MEDIA_CONTENT_TYPE: "music",
            ATTR_MEDIA_ANNOUNCE: True,
            ATTR_MEDIA_EXTRA: {"overlay_absolute_volume": 60},
        },
    )

    # Check API call
    mock_mozart_client.post_overlay_play.assert_called_once()

    # Check that the API call was as expected
    args, _ = mock_mozart_client.post_overlay_play.call_args
    assert args[0].volume_absolute == 60
    assert "/local/doorbell.mp3" in args[0].uri.location


async def test_async_play_media_overlay_invalid_offset_volume_tts(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_play_media with Home Assistant invalid offset volume and B&O tts."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    with patch(
        "homeassistant.components.bang_olufsen.media_player._LOGGER.warning"
    ) as mock_logger:
        await hass.services.async_call(
            "media_player",
            "play_media",
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
        )
        # Ensure that the logger has been called with the error message
        mock_logger.assert_called_once_with("Error setting volume")

    # Check API call
    mock_mozart_client.post_overlay_play.assert_called_once_with(
        TEST_OVERLAY_INVALID_OFFSET_VOLUME_TTS
    )


async def test_async_play_media_overlay_offset_volume_tts(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_play_media with Home Assistant invalid offset volume and B&O tts."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Set the volume to enable offset
    async_dispatcher_send(
        hass,
        f"{TEST_SERIAL_NUMBER}_{WebsocketNotification.VOLUME}",
        TEST_VOLUME,
    )

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "This is a test",
            ATTR_MEDIA_CONTENT_TYPE: "overlay_tts",
            ATTR_MEDIA_ANNOUNCE: True,
            ATTR_MEDIA_EXTRA: {"overlay_offset_volume": 20},
        },
    )

    # Check API call
    mock_mozart_client.post_overlay_play.assert_called_once_with(
        TEST_OVERLAY_OFFSET_VOLUME_TTS
    )


async def test_async_play_media_tts(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_play_media with Home Assistant tts."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Setup media source
    await async_setup_component(hass, "media_source", {"media_source": {}})

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/doorbell.mp3",
            ATTR_MEDIA_CONTENT_TYPE: "provider",
        },
    )

    # Check API call
    mock_mozart_client.post_overlay_play.assert_called_once()


async def test_async_play_media_radio(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_play_media with B&O radio."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "1234567890123456",
            ATTR_MEDIA_CONTENT_TYPE: "radio",
        },
    )

    # Check API call
    mock_mozart_client.run_provided_scene.assert_called_once_with(
        scene_properties=TEST_RADIO_STATION
    )


async def test_async_play_media_favourite(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_play_media with B&O favourite."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "1",
            ATTR_MEDIA_CONTENT_TYPE: "favourite",
        },
    )

    # Check API call
    mock_mozart_client.activate_preset.assert_called_once_with(id=int("1"))


async def test_async_play_media_deezer_flow(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_play_media with Deezer flow."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "flow",
            ATTR_MEDIA_CONTENT_TYPE: "deezer",
            ATTR_MEDIA_EXTRA: {"id": "123"},
        },
    )

    # Check API call
    mock_mozart_client.start_deezer_flow.assert_called_once_with(
        user_flow=TEST_DEEZER_FLOW
    )


async def test_async_play_media_deezer_playlist(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_play_media with Deezer playlist."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "playlist:1234567890",
            ATTR_MEDIA_CONTENT_TYPE: "deezer",
            ATTR_MEDIA_EXTRA: {"start_from": 123},
        },
    )

    # Check API call
    mock_mozart_client.add_to_queue.assert_called_once_with(
        play_queue_item=TEST_DEEZER_PLAYLIST
    )


async def test_async_play_media_deezer_track(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_play_media with Deezer track."""

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_ID: "1234567890",
            ATTR_MEDIA_CONTENT_TYPE: "deezer",
        },
    )

    # Check API call
    mock_mozart_client.add_to_queue.assert_called_once_with(
        play_queue_item=TEST_DEEZER_TRACK
    )


async def test_async_play_media_invalid_deezer(
    hass: HomeAssistant, mock_mozart_client, mock_config_entry
) -> None:
    """Test async_play_media with an invalid/no Deezer login."""
    mock_mozart_client.start_deezer_flow.side_effect = ApiException(
        status=400, reason="Bad Request"
    )

    # Setup entity
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Send a service call
    with patch(
        "homeassistant.components.bang_olufsen.media_player._LOGGER.error"
    ) as mock_logger:
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                ATTR_ENTITY_ID: TEST_MEDIA_PLAYER_ENTITY_ID,
                ATTR_MEDIA_CONTENT_ID: "flow",
                ATTR_MEDIA_CONTENT_TYPE: "deezer",
            },
        )
        # Ensure that the logger has been called with the error message
        mock_logger.assert_called_once()

    # # Check API call
    # mock_mozart_client.start_deezer_flow.assert_called_once_with(
    #     user_flow=TEST_DEEZER_FLOW
    # )
