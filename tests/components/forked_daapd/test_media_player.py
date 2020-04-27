"""The media player tests for the forked_daapd media player platform."""
from asyncio import TimeoutError as AsyncioTimeoutError, create_task, gather
from unittest.mock import patch

import pytest

from homeassistant.components.forked_daapd.const import (
    CONF_PIPE_CONTROL,
    CONF_PIPE_CONTROL_PORT,
    CONF_TTS_PAUSE_TIME,
    CONF_TTS_VOLUME,
    CONFIG_FLOW_UNIQUE_ID,
    DOMAIN,
    SUPPORTED_FEATURES,
    SUPPORTED_FEATURES_ZONE,
)
from homeassistant.components.media_player import (
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_PLAY_MEDIA,
    SERVICE_SHUFFLE_SET,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
)
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_TVSHOW,
)
from homeassistant.config_entries import CONN_CLASS_LOCAL_PUSH, SOURCE_USER
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_ON,
    STATE_PAUSED,
)

from tests.common import MockConfigEntry

TEST_MASTER_ENTITY_NAME = "media_player.forked_daapd_server"
TEST_ZONE_ENTITY_NAMES = [
    "media_player.forked_daapd_output_" + x
    for x in ["kitchen", "computer", "daapd_fifo"]
]
TEST_MASTER_FRIENDLY_NAME = "forked-daapd server"
TEST_ZONE_FRIENDLY_NAME = "forked-daapd output (kitchen)"

OPTIONS_DATA = {
    CONF_PIPE_CONTROL: "librespot-java",
    CONF_PIPE_CONTROL_PORT: "123",
    CONF_TTS_PAUSE_TIME: 0.5,
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

SAMPLE_TTS_QUEUE = {
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
            "length_ms": 50,
            "track_number": 1,
            "media_kind": "music",
            "uri": "tts_proxy_somefile.mp3",
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


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create hass config_entry fixture."""
    data = {
        CONF_HOST: "192.168.1.1",
        CONF_PORT: "2345",
        CONF_PASSWORD: "",
    }
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="",
        data=data,
        options={},
        system_options={},
        source=SOURCE_USER,
        connection_class=CONN_CLASS_LOCAL_PUSH,
        unique_id=CONFIG_FLOW_UNIQUE_ID,
        entry_id=1,
    )


@pytest.fixture(name="get_request_return_values")
async def get_request_return_values_fixture():
    """Get request return values we can change later."""
    return {
        "config": SAMPLE_CONFIG,
        "outputs": SAMPLE_OUTPUTS_ON,
        "player": SAMPLE_PLAYER_PAUSED,
        "queue": SAMPLE_TTS_QUEUE,
    }


@pytest.fixture(name="mock_api_object")
async def mock_api_object_fixture(hass, config_entry, get_request_return_values):
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
        config_entry.add_to_hass(hass)
        await config_entry.async_setup(hass)
        await hass.async_block_till_done()

    mock_api.return_value.start_websocket_handler.assert_called_once()
    mock_api.return_value.get_request.assert_called_once()
    updater_update = mock_api.return_value.start_websocket_handler.call_args[0][2]
    await updater_update(["player", "outputs", "queue"])
    await hass.async_block_till_done()

    async def add_to_queue_side_effect(uris, playback, playback_from_position=None):
        await updater_update(["queue", "player"])

    mock_api.return_value.add_to_queue.side_effect = (
        add_to_queue_side_effect  # for play_media testing
    )

    return mock_api.return_value


async def test_unload_config_entry(hass, config_entry, mock_api_object):
    """Test the player is removed when the config entry is unloaded."""
    assert hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert hass.states.get(TEST_ZONE_ENTITY_NAMES[0])
    await config_entry.async_unload(hass)
    assert not hass.states.get(TEST_MASTER_ENTITY_NAME)
    assert not hass.states.get(TEST_ZONE_ENTITY_NAMES[0])


def test_master_state(hass, mock_api_object):
    """Test master state attributes."""
    state = hass.states.get(TEST_MASTER_ENTITY_NAME)
    print(hass.states.get(TEST_ZONE_ENTITY_NAMES[0]))
    assert state.state == STATE_PAUSED
    assert state.attributes[ATTR_FRIENDLY_NAME] == TEST_MASTER_FRIENDLY_NAME
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORTED_FEATURES
    assert not state.attributes[ATTR_MEDIA_VOLUME_MUTED]
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.2
    assert state.attributes[ATTR_MEDIA_CONTENT_ID] == 12322
    assert state.attributes[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_MUSIC
    assert state.attributes[ATTR_MEDIA_DURATION] == 0.05
    assert state.attributes[ATTR_MEDIA_POSITION] == 0.005
    assert state.attributes[ATTR_MEDIA_TITLE] == "Short TTS file"
    assert state.attributes[ATTR_MEDIA_ARTIST] == "Google"
    assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == "No album"
    assert state.attributes[ATTR_MEDIA_ALBUM_ARTIST] == "The xx"
    assert state.attributes[ATTR_MEDIA_TRACK] == 1
    assert not state.attributes[ATTR_MEDIA_SHUFFLE]


async def _service_call(
    myhass, entity_name, service, additional_service_data=None, blocking=True
):
    if additional_service_data is None:
        additional_service_data = {}
    return await myhass.services.async_call(
        MP_DOMAIN,
        service,
        service_data={ATTR_ENTITY_ID: entity_name, **additional_service_data},
        blocking=blocking,
    )


async def test_zone(hass, mock_api_object):
    """Test zone attributes and methods."""
    zone_entity_name = TEST_ZONE_ENTITY_NAMES[0]
    state = hass.states.get(zone_entity_name)
    assert state.attributes[ATTR_FRIENDLY_NAME] == TEST_ZONE_FRIENDLY_NAME
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


async def test_last_outputs_master(hass, mock_api_object):
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


async def test_bunch_of_stuff_master(hass, mock_api_object, get_request_return_values):
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
    # test media play
    with patch(
        "homeassistant.components.forked_daapd.media_player.asyncio.sleep",
        autospec=True,
    ):
        task = _service_call(
            hass,
            TEST_MASTER_ENTITY_NAME,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: "somefile.mp3",
            },
            blocking=False,
        )  # don't block and gather task later so hass_async_block_till_done() calls inside _update don't get stuck
        await gather(task)
        await hass.async_block_till_done()
        # try playing unsupported media type
        await _service_call(
            hass,
            TEST_MASTER_ENTITY_NAME,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_TVSHOW,
                ATTR_MEDIA_CONTENT_ID: "wontwork.mp4",
            },
        )

        # throw timeout error in media play
        def timeout_side_effect(coro, timeout=None):
            create_task(coro).cancel()
            raise AsyncioTimeoutError

        with patch("asyncio.wait_for", autospec=True) as wait_for_mock:
            wait_for_mock.side_effect = timeout_side_effect
            task = _service_call(
                hass,
                TEST_MASTER_ENTITY_NAME,
                SERVICE_PLAY_MEDIA,
                {
                    ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                    ATTR_MEDIA_CONTENT_ID: "somefile.mp3",
                },
                blocking=False,
            )
            await gather(task)
            await hass.async_block_till_done()


async def test_librespot_java_stuff(
    hass, mock_api_object, config_entry, get_request_return_values
):
    """Test options update and librespot-java stuff."""
    with patch(
        "homeassistant.components.forked_daapd.media_player.LibrespotJavaAPI",
        autospec=True,
    ):
        hass.config_entries.async_update_entry(config_entry, options=OPTIONS_DATA)
        await hass.async_block_till_done()
    get_request_return_values["player"] = SAMPLE_PLAYER_PLAYING
    updater_update = mock_api_object.start_websocket_handler.call_args[0][2]
    await updater_update(["player"])
    # test media play
    with patch(
        "homeassistant.components.forked_daapd.media_player.asyncio.sleep",
        autospec=True,
    ):
        task = _service_call(
            hass,
            TEST_MASTER_ENTITY_NAME,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: "somefile.mp3",
            },
            blocking=False,
        )  # don't block and gather task later so hass_async_block_till_done() calls inside _update don't get stuck
        await gather(task)
        await hass.async_block_till_done()
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_MEDIA_PREVIOUS_TRACK)
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_MEDIA_NEXT_TRACK)
    await _service_call(hass, TEST_MASTER_ENTITY_NAME, SERVICE_MEDIA_PLAY)


async def test_unsupported_update(mock_api_object):
    """Test unsupported but known update type."""
    updater_update = mock_api_object.start_websocket_handler.call_args[0][2]
    await updater_update(["database"])


async def test_invalid_websocket_port(hass, config_entry):
    """Test invalid websocket port on async_init."""
    with patch(
        "homeassistant.components.forked_daapd.media_player.ForkedDaapdAPI",
        autospec=True,
    ) as mock_api:
        mock_api.return_value.get_request.return_value = SAMPLE_CONFIG_NO_WEBSOCKET
        config_entry.add_to_hass(hass)
        await config_entry.async_setup(hass)
        await hass.async_block_till_done()
        print(mock_api.return_value.get_request.call_args)


async def test_websocket_disconnect(hass, mock_api_object):
    """Test websocket disconnection."""
    updater_disconnected = mock_api_object.start_websocket_handler.call_args[0][4]
    updater_disconnected()
    await hass.async_block_till_done()
