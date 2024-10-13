"""The media player tests for the forked_daapd media player platform."""

from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.forked_daapd.browse_media import create_media_content_id
from homeassistant.components.forked_daapd.const import (
    CONF_LIBRESPOT_JAVA_PORT,
    CONF_MAX_PLAYLISTS,
    CONF_TTS_PAUSE_TIME,
    CONF_TTS_VOLUME,
    SIGNAL_UPDATE_OUTPUTS,
    SIGNAL_UPDATE_PLAYER,
    SIGNAL_UPDATE_QUEUE,
    SOURCE_NAME_CLEAR,
    SOURCE_NAME_DEFAULT,
    SUPPORTED_FEATURES,
    SUPPORTED_FEATURES_ZONE,
)
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SERVICE_SHUFFLE_SET,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    MediaPlayerEnqueue,
    MediaType,
)
from homeassistant.components.media_source import PlayMedia
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    STATE_ON,
    STATE_PAUSED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, ServiceResponse

from tests.common import MockConfigEntry, async_mock_signal

TEST_MASTER_ENTITY_NAME = "media_player.owntone_server"
TEST_ZONE_ENTITY_NAMES = [
    "media_player.owntone_output_" + x for x in ("kitchen", "computer", "daapd_fifo")
]

OPTIONS_DATA = {
    CONF_LIBRESPOT_JAVA_PORT: "123",
    CONF_MAX_PLAYLISTS: 8,
    CONF_TTS_PAUSE_TIME: 0,
    CONF_TTS_VOLUME: 0.25,
}

SAMPLE_PLAYER_PAUSED = {
    "state": "pause",
    "repeat": "off",
    "consume": False,
    "shuffle": False,
    "volume": 20,
    "item_id": 12322,
    "item_length_ms": 50,
    "item_progress_ms": 5,
}

SAMPLE_PLAYER_PLAYING = {
    "state": "play",
    "repeat": "off",
    "consume": False,
    "shuffle": False,
    "volume": 50,
    "item_id": 12322,
    "item_length_ms": 50,
    "item_progress_ms": 5,
}

SAMPLE_PLAYER_STOPPED = {
    "state": "stop",
    "repeat": "off",
    "consume": False,
    "shuffle": False,
    "volume": 0,
    "item_id": 12322,
    "item_length_ms": 50,
    "item_progress_ms": 5,
}

SAMPLE_QUEUE = {
    "version": 833,
    "count": 1,
    "items": [
        {
            "id": 12322,
            "position": 0,
            "track_id": 1234,
            "title": "Some song",
            "artist": "Some artist",
            "album": "No album",
            "album_artist": "The xx",
            "artwork_url": "http://art",
            "length_ms": 0,
            "track_number": 1,
            "media_kind": "music",
            "data_kind": "url",
            "uri": "library:track:5",
        }
    ],
}

SAMPLE_QUEUE_TTS = {
    "version": 833,
    "count": 1,
    "items": [
        {
            "id": 12322,
            "position": 0,
            "track_id": 1234,
            "title": "Short TTS file",
            "artist": "Google",
            "album": "No album",
            "album_artist": "The xx",
            "artwork_url": "http://art",
            "length_ms": 0,
            "track_number": 1,
            "media_kind": "music",
            "data_kind": "url",
            "uri": "tts_proxy_somefile.mp3",
        }
    ],
}

SAMPLE_QUEUE_PIPE = {
    "version": 833,
    "count": 1,
    "items": [
        {
            "id": 12322,
            "title": "librespot-java",
            "artist": "some artist",
            "album": "some album",
            "album_artist": "The xx",
            "length_ms": 0,
            "track_number": 1,
            "media_kind": "music",
            "data_kind": "pipe",
            "uri": "pipeuri",
        }
    ],
}

SAMPLE_CONFIG = {
    "websocket_port": 3688,
    "version": "25.0",
    "buildoptions": [
        "ffmpeg",
        "iTunes XML",
        "Spotify",
        "LastFM",
        "MPD",
        "Device verification",
        "Websockets",
        "ALSA",
    ],
}

SAMPLE_CONFIG_NO_WEBSOCKET = {
    "websocket_port": 0,
    "version": "25.0",
    "buildoptions": [
        "ffmpeg",
        "iTunes XML",
        "Spotify",
        "LastFM",
        "MPD",
        "Device verification",
        "Websockets",
        "ALSA",
    ],
}


SAMPLE_OUTPUTS_ON = (
    {
        "id": "123456789012345",
        "name": "kitchen",
        "type": "AirPlay",
        "selected": True,
        "has_password": False,
        "requires_auth": False,
        "needs_auth_key": False,
        "volume": 50,
    },
    {
        "id": "0",
        "name": "Computer",
        "type": "ALSA",
        "selected": True,
        "has_password": False,
        "requires_auth": False,
        "needs_auth_key": False,
        "volume": 19,
    },
    {
        "id": "100",
        "name": "daapd-fifo",
        "type": "fifo",
        "selected": False,
        "has_password": False,
        "requires_auth": False,
        "needs_auth_key": False,
        "volume": 0,
    },
)


SAMPLE_OUTPUTS_UNSELECTED = [
    {
        "id": "123456789012345",
        "name": "kitchen",
        "type": "AirPlay",
        "selected": False,
        "has_password": False,
        "requires_auth": False,
        "needs_auth_key": False,
        "volume": 0,
    },
    {
        "id": "0",
        "name": "Computer",
        "type": "ALSA",
        "selected": False,
        "has_password": False,
        "requires_auth": False,
        "needs_auth_key": False,
        "volume": 19,
    },
    {
        "id": "100",
        "name": "daapd-fifo",
        "type": "fifo",
        "selected": False,
        "has_password": False,
        "requires_auth": False,
        "needs_auth_key": False,
        "volume": 0,
    },
]

SAMPLE_PIPES = [
    {
        "id": 1,
        "title": "librespot-java",
        "media_kind": "music",
        "data_kind": "pipe",
        "path": "/music/srv/input.pipe",
        "uri": "library:track:1",
    }
]

SAMPLE_PLAYLISTS = [{"id": 7, "name": "test_playlist", "uri": "library:playlist:2"}]


@pytest.fixture(name="get_request_return_values")
async def get_request_return_values_fixture() -> dict[str, Any]:
    """Get request return values we can change later."""
    return {
        "config": SAMPLE_CONFIG,
        "outputs": SAMPLE_OUTPUTS_ON,
        "player": SAMPLE_PLAYER_PAUSED,
        "queue": SAMPLE_QUEUE,
    }


@pytest.fixture(name="mock_api_object")
async def mock_api_object_fixture(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    get_request_return_values: dict[str, Any],
) -> Mock:
    """Create mock api fixture."""

    async def get_request_side_effect(update_type):
        if update_type == "outputs":
            return {"outputs": get_request_return_values["outputs"]}
        return get_request_return_values[update_type]

    with patch(
        "homeassistant.components.forked_daapd.media_player.ForkedDaapdAPI",
        autospec=True,
    ) as mock_api:
        mock_api.return_value.get_request.side_effect = get_request_side_effect
        mock_api.return_value.full_url.return_value = ""
        mock_api.return_value.get_pipes.return_value = SAMPLE_PIPES
        mock_api.return_value.get_playlists.return_value = SAMPLE_PLAYLISTS
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    mock_api.return_value.start_websocket_handler.assert_called_once()
    mock_api.return_value.get_request.assert_called_once()
    updater_update = mock_api.return_value.start_websocket_handler.call_args[0][2]
    await updater_update(["player", "outputs", "queue"])
    await hass.async_block_till_done()

    async def add_to_queue_side_effect(
        uris, playback=None, position=None, playback_from_position=None, clear=None
    ):
        await updater_update(["queue", "player"])

    # for play_media testing
    mock_api.return_value.add_to_queue.side_effect = add_to_queue_side_effect

    async def pause_side_effect():
        await updater_update(["player"])

    mock_api.return_value.pause_playback.side_effect = pause_side_effect

    return mock_api.return_value


@pytest.mark.usefixtures("mock_api_object")
async def test_unload_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the player is set unavailable when the config entry is unloaded."""
    assert hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert hass.states.get(TEST_ZONE_ENTITY_NAMES[0])
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert hass.states.get(TEST_MASTER_ENTITY_NAME).state == STATE_UNAVAILABLE
    assert hass.states.get(TEST_ZONE_ENTITY_NAMES[0]).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_api_object")
def test_master_state(hass: HomeAssistant) -> None:
    """Test master state attributes."""
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.state == STATE_PAUSED
    assert state.attributes[ATTR_FRIENDLY_NAME] == "OwnTone server"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORTED_FEATURES
    assert not state.attributes[ATTR_MEDIA_VOLUME_MUTED]
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.2
    assert state.attributes[ATTR_MEDIA_CONTENT_ID] == 12322
    assert state.attributes[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert state.attributes[ATTR_MEDIA_DURATION] == 0.05
    assert state.attributes[ATTR_MEDIA_POSITION] == 0.005
    assert state.attributes[ATTR_MEDIA_TITLE] == "No album"  # reversed for url
    assert state.attributes[ATTR_MEDIA_ARTIST] == "Some artist"
    assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == "Some song"  # reversed
    assert state.attributes[ATTR_MEDIA_ALBUM_ARTIST] == "The xx"
    assert state.attributes[ATTR_MEDIA_TRACK] == 1
    assert not state.attributes[ATTR_MEDIA_SHUFFLE]


async def test_no_update_when_get_request_returns_none(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api_object: Mock
) -> None:
    """Test when get request returns None."""

    async def get_request_side_effect(update_type):
        return None

    mock_api_object.get_request.side_effect = get_request_side_effect
    updater_update = mock_api_object.start_websocket_handler.call_args[0][2]
    signal_output_call = async_mock_signal(
        hass, SIGNAL_UPDATE_OUTPUTS.format(config_entry.entry_id)
    )
    signal_player_call = async_mock_signal(
        hass, SIGNAL_UPDATE_PLAYER.format(config_entry.entry_id)
    )
    signal_queue_call = async_mock_signal(
        hass, SIGNAL_UPDATE_QUEUE.format(config_entry.entry_id)
    )
    await updater_update(["outputs", "player", "queue"])
    await hass.async_block_till_done()
    assert len(signal_output_call) == 0
    assert len(signal_player_call) == 0
    assert len(signal_queue_call) == 0


async def _service_call(
    hass: HomeAssistant,
    entity_name: str,
    service: str,
    additional_service_data: dict[str, Any] | None = None,
    blocking: bool = True,
) -> ServiceResponse:
    if additional_service_data is None:
        additional_service_data = {}
    return await hass.services.async_call(
        MP_DOMAIN,
        service,
        service_data={ATTR_ENTITY_ID: entity_name, **additional_service_data},
        blocking=blocking,
    )


async def test_zone(hass: HomeAssistant, mock_api_object: Mock) -> None:
    """Test zone attributes and methods."""
    zone_entity_name = TEST_ZONE_ENTITY_NAMES[0]
    state = hass.states.get(zone_entity_name)
    assert state.attributes[ATTR_FRIENDLY_NAME] == "OwnTone output (kitchen)"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORTED_FEATURES_ZONE
    assert state.state == STATE_ON
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.5
    assert not state.attributes[ATTR_MEDIA_VOLUME_MUTED]
    await _service_call(hass, zone_entity_name, SERVICE_TURN_ON)
    await _service_call(hass, zone_entity_name, SERVICE_TURN_OFF)
    await _service_call(hass, zone_entity_name, SERVICE_TOGGLE)
    await _service_call(
        hass, zone_entity_name, SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0.3}
    )
    await _service_call(
        hass, zone_entity_name, SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}
    )
    await _service_call(
        hass, zone_entity_name, SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: False}
    )
    zone_entity_name = TEST_ZONE_ENTITY_NAMES[2]
    await _service_call(hass, zone_entity_name, SERVICE_TOGGLE)
    await _service_call(
        hass, zone_entity_name, SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}
    )
    output_id = SAMPLE_OUTPUTS_ON[0]["id"]
    initial_volume = SAMPLE_OUTPUTS_ON[0]["volume"]
    mock_api_object.change_output.assert_any_call(output_id, selected=True)
    mock_api_object.change_output.assert_any_call(output_id, selected=False)
    mock_api_object.set_volume.assert_any_call(output_id=output_id, volume=30)
    mock_api_object.set_volume.assert_any_call(output_id=output_id, volume=0)
    mock_api_object.set_volume.assert_any_call(
        output_id=output_id, volume=initial_volume
    )
    output_id = SAMPLE_OUTPUTS_ON[2]["id"]
    mock_api_object.change_output.assert_any_call(output_id, selected=True)


async def test_last_outputs_master(hass: HomeAssistant, mock_api_object: Mock) -> None:
    """Test restoration of _last_outputs."""
    # Test turning on sends API call
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_TURN_ON)
    assert mock_api_object.change_output.call_count == 0
    assert mock_api_object.set_enabled_outputs.call_count == 1
    await _service_call(
        hass, TEST_MASTER_ENTITY_NAME, SERVICE_TURN_OFF
    )  # should have stored last outputs
    assert mock_api_object.change_output.call_count == 0
    assert mock_api_object.set_enabled_outputs.call_count == 2
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_TURN_ON)
    assert mock_api_object.change_output.call_count == 3
    assert mock_api_object.set_enabled_outputs.call_count == 2


async def test_bunch_of_stuff_master(
    hass: HomeAssistant,
    get_request_return_values: dict[str, Any],
    mock_api_object: Mock,
) -> None:
    """Run bunch of stuff."""
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_TURN_ON)
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_TURN_OFF)
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_TOGGLE)
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_VOLUME_MUTE,
        {ATTR_MEDIA_VOLUME_MUTED: True},
    )
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_VOLUME_MUTE,
        {ATTR_MEDIA_VOLUME_MUTED: False},
    )
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_VOLUME_SET,
        {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
    )
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_MEDIA_PAUSE)
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_MEDIA_PLAY)
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_MEDIA_STOP)
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_MEDIA_PREVIOUS_TRACK)
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_MEDIA_NEXT_TRACK)
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_MEDIA_SEEK,
        {ATTR_MEDIA_SEEK_POSITION: 35},
    )
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_CLEAR_PLAYLIST)
    await _service_call(
        hass, TEST_MASTER_ENTITY_NAME, SERVICE_SHUFFLE_SET, {ATTR_MEDIA_SHUFFLE: False}
    )
    # stop player and run more stuff
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.2
    get_request_return_values["player"] = SAMPLE_PLAYER_STOPPED
    updater_update = mock_api_object.start_websocket_handler.call_args[0][2]
    await updater_update(["player"])
    await hass.async_block_till_done()
    # mute from volume==0
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_VOLUME_MUTE,
        {ATTR_MEDIA_VOLUME_MUTED: True},
    )
    # now turn off (stopped and all outputs unselected)
    get_request_return_values["outputs"] = SAMPLE_OUTPUTS_UNSELECTED
    await updater_update(["outputs"])
    await hass.async_block_till_done()
    # toggle from off
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_TOGGLE)
    for output in SAMPLE_OUTPUTS_ON:
        mock_api_object.change_output.assert_any_call(
            output["id"],
            selected=output["selected"],
            volume=output["volume"],
        )
    mock_api_object.set_volume.assert_any_call(volume=0)
    mock_api_object.set_volume.assert_any_call(volume=SAMPLE_PLAYER_PAUSED["volume"])
    mock_api_object.set_volume.assert_any_call(volume=50)
    mock_api_object.set_enabled_outputs.assert_any_call(
        [output["id"] for output in SAMPLE_OUTPUTS_ON]
    )
    mock_api_object.set_enabled_outputs.assert_any_call([])
    mock_api_object.start_playback.assert_called_once()
    assert mock_api_object.pause_playback.call_count == 3
    mock_api_object.stop_playback.assert_called_once()
    mock_api_object.previous_track.assert_called_once()
    mock_api_object.next_track.assert_called_once()
    mock_api_object.seek.assert_called_once()
    mock_api_object.shuffle.assert_called_once()
    mock_api_object.clear_queue.assert_called_once()


@pytest.mark.usefixtures("mock_api_object")
async def test_async_play_media_from_paused(hass: HomeAssistant) -> None:
    """Test async play media from paused."""
    initial_state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "http://example.com/somefile.mp3",
        },
    )
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.state == initial_state.state
    assert state.last_updated > initial_state.last_updated


async def test_async_play_media_announcement_from_stopped(
    hass: HomeAssistant,
    get_request_return_values: dict[str, Any],
    mock_api_object: Mock,
) -> None:
    """Test async play media announcement (from stopped)."""
    updater_update = mock_api_object.start_websocket_handler.call_args[0][2]

    get_request_return_values["player"] = SAMPLE_PLAYER_STOPPED
    await updater_update(["player"])
    await hass.async_block_till_done()
    initial_state = hass.states.get(TEST_MASTER_ENTITY_NAME)

    get_request_return_values["queue"] = SAMPLE_QUEUE_TTS
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "http://example.com/somefile.mp3",
            ATTR_MEDIA_ANNOUNCE: True,
        },
    )
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.state == initial_state.state
    assert state.last_updated > initial_state.last_updated


@pytest.mark.usefixtures("mock_api_object")
async def test_async_play_media_unsupported(hass: HomeAssistant) -> None:
    """Test async play media on unsupported media type."""
    initial_state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: MediaType.TVSHOW,
            ATTR_MEDIA_CONTENT_ID: "wontwork.mp4",
        },
    )
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.last_updated == initial_state.last_updated


async def test_async_play_media_announcement_tts_timeout(
    hass: HomeAssistant, mock_api_object: Mock
) -> None:
    """Test async play media announcement with TTS timeout."""
    mock_api_object.add_to_queue.side_effect = None
    with patch("homeassistant.components.forked_daapd.media_player.TTS_TIMEOUT", 0):
        initial_state = hass.states.get(TEST_MASTER_ENTITY_NAME)
        await _service_call(
            hass,
            TEST_MASTER_ENTITY_NAME,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "http://example.com/somefile.mp3",
                ATTR_MEDIA_ANNOUNCE: True,
            },
        )
        state = hass.states.get(TEST_MASTER_ENTITY_NAME)
        assert state.state == initial_state.state
        assert state.last_updated > initial_state.last_updated


async def test_use_pipe_control_with_no_api(
    hass: HomeAssistant, mock_api_object: Mock
) -> None:
    """Test using pipe control with no api set."""
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: "librespot-java (pipe)"},
    )
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_MEDIA_PLAY)
    assert mock_api_object.start_playback.call_count == 0


@pytest.mark.usefixtures("mock_api_object")
async def test_clear_source(hass: HomeAssistant) -> None:
    """Test changing source to clear."""
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: SOURCE_NAME_CLEAR},
    )
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.attributes[ATTR_INPUT_SOURCE] == SOURCE_NAME_DEFAULT


@pytest.fixture(name="pipe_control_api_object")
async def pipe_control_api_object_fixture(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    get_request_return_values: dict[str, Any],
    mock_api_object: Mock,
) -> Mock:
    """Fixture for mock librespot_java api."""
    with patch(
        "homeassistant.components.forked_daapd.media_player.LibrespotJavaAPI",
        autospec=True,
    ) as pipe_control_api:
        hass.config_entries.async_update_entry(config_entry, options=OPTIONS_DATA)
        await hass.async_block_till_done()
    get_request_return_values["player"] = SAMPLE_PLAYER_PLAYING
    updater_update = mock_api_object.start_websocket_handler.call_args[0][2]
    await updater_update(["player"])
    await hass.async_block_till_done()

    async def pause_side_effect():
        await updater_update(["player"])

    pipe_control_api.return_value.player_pause.side_effect = pause_side_effect

    await updater_update(["database"])  # load in sources
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: "librespot-java (pipe)"},
    )

    return pipe_control_api.return_value


async def test_librespot_java_stuff(
    hass: HomeAssistant,
    get_request_return_values: dict[str, Any],
    mock_api_object: Mock,
    pipe_control_api_object: Mock,
) -> None:
    """Test options update and librespot-java stuff."""
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.attributes[ATTR_INPUT_SOURCE] == "librespot-java (pipe)"
    # call some basic services
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_MEDIA_STOP)
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_MEDIA_PREVIOUS_TRACK)
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_MEDIA_NEXT_TRACK)
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_MEDIA_PLAY)
    pipe_control_api_object.player_pause.assert_called_once()
    pipe_control_api_object.player_prev.assert_called_once()
    pipe_control_api_object.player_next.assert_called_once()
    pipe_control_api_object.player_resume.assert_called_once()
    # switch away
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: SOURCE_NAME_DEFAULT},
    )
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.attributes[ATTR_INPUT_SOURCE] == SOURCE_NAME_DEFAULT
    # test pipe getting queued externally changes source
    get_request_return_values["queue"] = SAMPLE_QUEUE_PIPE
    updater_update = mock_api_object.start_websocket_handler.call_args[0][2]
    await updater_update(["queue"])
    await hass.async_block_till_done()
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.attributes[ATTR_INPUT_SOURCE] == "librespot-java (pipe)"
    # test title and album not reversed when data_kind not url
    assert state.attributes[ATTR_MEDIA_TITLE] == "librespot-java"
    assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == "some album"


@pytest.mark.usefixtures("pipe_control_api_object")
async def test_librespot_java_play_announcement(hass: HomeAssistant) -> None:
    """Test play announcement with librespot-java pipe."""
    initial_state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "http://example.com/somefile.mp3",
            ATTR_MEDIA_ANNOUNCE: True,
        },
    )
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.state == initial_state.state
    assert state.last_updated > initial_state.last_updated


async def test_librespot_java_play_media_pause_timeout(
    hass: HomeAssistant, pipe_control_api_object: Mock
) -> None:
    """Test play media with librespot-java pipe."""
    # test media play with pause timeout
    pipe_control_api_object.player_pause.side_effect = None
    with patch(
        "homeassistant.components.forked_daapd.media_player.CALLBACK_TIMEOUT", 0
    ):
        initial_state = hass.states.get(TEST_MASTER_ENTITY_NAME)
        await _service_call(
            hass,
            TEST_MASTER_ENTITY_NAME,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "http://example.com/somefile.mp3",
            },
        )
        state = hass.states.get(TEST_MASTER_ENTITY_NAME)
        assert state.state == initial_state.state
        assert state.last_updated > initial_state.last_updated


async def test_unsupported_update(hass: HomeAssistant, mock_api_object: Mock) -> None:
    """Test unsupported update type."""
    last_updated = hass.states.get(TEST_MASTER_ENTITY_NAME).last_updated
    updater_update = mock_api_object.start_websocket_handler.call_args[0][2]
    await updater_update(["config"])
    await hass.async_block_till_done()
    assert hass.states.get(TEST_MASTER_ENTITY_NAME).last_updated == last_updated


async def test_invalid_websocket_port(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test invalid websocket port on async_init."""
    with patch(
        "homeassistant.components.forked_daapd.media_player.ForkedDaapdAPI",
        autospec=True,
    ) as mock_api:
        mock_api.return_value.get_request.return_value = SAMPLE_CONFIG_NO_WEBSOCKET
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(TEST_MASTER_ENTITY_NAME).state == STATE_UNAVAILABLE


async def test_websocket_disconnect(hass: HomeAssistant, mock_api_object: Mock) -> None:
    """Test websocket disconnection."""
    assert hass.states.get(TEST_MASTER_ENTITY_NAME).state != STATE_UNAVAILABLE
    assert hass.states.get(TEST_ZONE_ENTITY_NAMES[0]).state != STATE_UNAVAILABLE
    updater_disconnected = mock_api_object.start_websocket_handler.call_args[0][4]
    await updater_disconnected()
    await hass.async_block_till_done()
    assert hass.states.get(TEST_MASTER_ENTITY_NAME).state == STATE_UNAVAILABLE
    assert hass.states.get(TEST_ZONE_ENTITY_NAMES[0]).state == STATE_UNAVAILABLE


async def test_async_play_media_enqueue(
    hass: HomeAssistant, mock_api_object: Mock
) -> None:
    """Test async play media with different enqueue options."""
    initial_state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "http://example.com/play.mp3",
            ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.PLAY,
        },
    )
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.state == initial_state.state
    assert state.last_updated > initial_state.last_updated
    mock_api_object.add_to_queue.assert_called_with(
        uris="http://example.com/play.mp3",
        playback="start",
        position=0,
        playback_from_position=0,
    )
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "http://example.com/replace.mp3",
            ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.REPLACE,
        },
    )
    mock_api_object.add_to_queue.assert_called_with(
        uris="http://example.com/replace.mp3", playback="start", clear=True
    )
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "http://example.com/add.mp3",
            ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.ADD,
        },
    )
    mock_api_object.add_to_queue.assert_called_with(
        uris="http://example.com/add.mp3", playback="start", clear=False
    )
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "http://example.com/add.mp3",
            ATTR_MEDIA_ENQUEUE: True,
        },
    )
    mock_api_object.add_to_queue.assert_called_with(
        uris="http://example.com/add.mp3", playback="start", clear=False
    )
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "http://example.com/next.mp3",
            ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.NEXT,
        },
    )
    mock_api_object.add_to_queue.assert_called_with(
        uris="http://example.com/next.mp3", playback="start", position=1
    )


async def test_play_owntone_media(hass: HomeAssistant, mock_api_object: Mock) -> None:
    """Test async play media with an owntone source."""
    initial_state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: create_media_content_id(
                "some song", "library:track:456"
            ),
            ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.PLAY,
        },
    )
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.state == initial_state.state
    assert state.last_updated > initial_state.last_updated
    mock_api_object.add_to_queue.assert_called_with(
        uris="library:track:456",
        playback="start",
        position=0,
        playback_from_position=0,
    )


async def test_play_spotify_media(hass: HomeAssistant, mock_api_object: Mock) -> None:
    """Test async play media with a spotify source."""
    initial_state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    await _service_call(
        hass,
        TEST_MASTER_ENTITY_NAME,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: "spotify://track",
            ATTR_MEDIA_CONTENT_ID: "spotify://open.spotify.com/spotify:track:abcdefghi",
            ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.PLAY,
        },
    )
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.state == initial_state.state
    assert state.last_updated > initial_state.last_updated
    mock_api_object.add_to_queue.assert_called_with(
        uris="spotify:track:abcdefghi",
        playback="start",
        position=0,
        playback_from_position=0,
    )


async def test_play_media_source(hass: HomeAssistant, mock_api_object: Mock) -> None:
    """Test async play media with a spotify source."""
    initial_state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        return_value=PlayMedia("http://my_hass/song.m4a", "audio/aac"),
    ):
        await _service_call(
            hass,
            TEST_MASTER_ENTITY_NAME,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_MEDIA_CONTENT_TYPE: "audio/aac",
                ATTR_MEDIA_CONTENT_ID: "media-source://media_source/test_dir/song.m4a",
                ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.PLAY,
            },
        )
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert state.state == initial_state.state
    assert state.last_updated > initial_state.last_updated
    mock_api_object.add_to_queue.assert_called_with(
        uris="http://my_hass/song.m4a",
        playback="start",
        position=0,
        playback_from_position=0,
    )
