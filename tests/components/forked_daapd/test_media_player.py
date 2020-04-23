"""The tests for the forked_daapd media player platform."""
from asyncio import Future, TimeoutError as AsyncioTimeoutError, create_task

from asynctest.mock import patch
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.forked_daapd.const import (
    CONF_DEFAULT_VOLUME,
    CONF_PIPE_CONTROL,
    CONF_PIPE_CONTROL_PORT,
    CONF_TTS_PAUSE_TIME,
    CONF_TTS_VOLUME,
    CONFIG_FLOW_UNIQUE_ID,
    DOMAIN,
    FD_NAME,
    HASS_DATA_MASTER_KEY,
    HASS_DATA_OUTPUTS_KEY,
    SUPPORTED_FEATURES,
    SUPPORTED_FEATURES_ZONE,
)
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_TVSHOW,
)
from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_PUSH,
    SOURCE_USER,
    SOURCE_ZEROCONF,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_ON,
    STATE_PAUSED,
)

from tests.common import MockConfigEntry

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


SAMPLE_QUEUE = {
    "version": 833,
    "count": 3,
    "items": [
        {
            "id": 12122,
            "position": 1,
            "track_id": 10749,
            "title": "Angels",
            "artist": "The xx",
            "artist_sort": "xx, The",
            "album": "Coexist",
            "album_sort": "Coexist",
            "album_artist": "The xx",
            "album_artist_sort": "xx, The",
            "genre": "Indie Rock",
            "year": 2012,
            "track_number": 1,
            "disc_number": 1,
            "length_ms": 171735,
            "media_kind": "music",
            "data_kind": "file",
            "path": "/music/srv/The xx/Coexist/01 Angels.mp3",
            "uri": "library:track:10749",
        },
        {
            "id": 13425,
            "position": 2,
            "track_id": 5149,
            "title": "Dummy Title",
            "artist": "Dummy artist",
            "artist_sort": "xx, The",
            "album": "Dummy album",
            "album_sort": "Dummy sort",
            "album_artist": "Dummy album artist",
            "album_artist_sort": "xx, The",
            "genre": "Indie Rock",
            "year": 2010,
            "track_number": 3,
            "disc_number": 3,
            "length_ms": 209735,
            "media_kind": "music",
            "data_kind": "file",
            "path": "/music/srv/dummy/dummy.mp3",
            "uri": "library:track:5149",
        },
        {
            "id": 12322,
            "position": 0,
            "track_id": 1234,
            "title": "Short TTS file",
            "track_number": 1,
            "artist": "Google",
            "album": "No album",
            "album_artist": "The xx",
            "length_ms": 50,
            "artwork_url": "myuri",  # test with and without artwork
            "media_kind": "music",
            "uri": "tts_proxy_somefile.mp3",
        },
    ],
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
        CONF_DEFAULT_VOLUME: 0.5,
        CONF_NAME: "Test Server",
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


@pytest.fixture(name="master")
async def master_fixture(hass, config_entry, get_request_return_values):
    """Create master device fixture."""

    async def get_request_side_effect(update_type):
        if update_type == "outputs":
            return {"outputs": get_request_return_values["outputs"]}
        return get_request_return_values[update_type]

    async def add_to_queue_side_effect(uris, playback, playback_from_position=None):
        await master._updater._update(["queue", "player"])  # sorry for touching private

    with patch(
        "homeassistant.components.forked_daapd.media_player.ForkedDaapdAPI",
        autospec=True,
    ) as mock_api:
        mock_api.return_value.get_request.side_effect = get_request_side_effect
        mock_api.return_value.add_to_queue.side_effect = add_to_queue_side_effect
        hass.config_entries._entries.append(config_entry)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        master = hass.data[DOMAIN][HASS_DATA_MASTER_KEY]
        await master._updater._update(["player", "outputs", "queue"])
        await hass.async_block_till_done()
    return master


async def test_unload_config_entry(hass, config_entry, master):
    """Test the player is removed when the config entry is unloaded."""
    zone = hass.data[DOMAIN][HASS_DATA_OUTPUTS_KEY][0]
    master_entity_name = (
        "media_player."
        + master.name.replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
        .lower()
    )
    zone_entity_name = (
        "media_player."
        + zone.name.replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
        .lower()
    )
    assert hass.states.get(master_entity_name)
    assert hass.states.get(zone_entity_name)
    await config_entry.async_unload(hass)
    assert not hass.states.get(master_entity_name)
    assert not hass.states.get(zone_entity_name)


def test_master_state(hass, master):
    """Test master state attributes."""
    state = hass.states.get(
        "media_player."
        + master.name.replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
        .lower()
    )
    assert state.state == STATE_PAUSED
    assert state.attributes[ATTR_FRIENDLY_NAME] == master.name
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


async def test_zone(hass, master, get_request_return_values):
    """Test zone attributes and methods."""
    zone = hass.data[DOMAIN][HASS_DATA_OUTPUTS_KEY][0]
    state = hass.states.get(
        "media_player."
        + zone.name.replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
        .lower()
    )
    assert state.attributes[ATTR_FRIENDLY_NAME] == zone.name
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORTED_FEATURES_ZONE
    assert state.state == STATE_ON
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.5
    assert not state.attributes[ATTR_MEDIA_VOLUME_MUTED]
    await zone.async_turn_on()
    await zone.async_turn_off()
    await zone.async_toggle()
    await zone.async_set_volume_level(0.3)
    await zone.async_mute_volume(True)
    await zone.async_mute_volume(False)
    await zone.async_remove()
    # load in different output test more
    zone = hass.data[DOMAIN][HASS_DATA_OUTPUTS_KEY][1]
    await zone.async_toggle()
    await zone.async_mute_volume(True)


async def test_last_outputs_master(master, get_request_return_values):
    """Test restoration of _last_outputs."""
    # Test turning on sends API call with no last_outputs
    assert master._last_outputs is None  # sorry for touching private
    await master.async_turn_on()
    assert master._api.set_enabled_outputs.call_count == 1  # sorry for touching private
    await master.async_turn_off()  # should have stored last outputs
    await master.async_turn_on()
    assert master._api.change_output.call_count == len(
        SAMPLE_OUTPUTS_UNSELECTED
    )  # sorry for touching private


async def test_bunch_of_stuff_master(master, get_request_return_values):
    """Run bunch of stuff."""
    await master.async_turn_on()
    await master.async_turn_off()
    await master.async_toggle()
    await master.async_mute_volume(True)
    await master.async_mute_volume(False)
    await master.async_set_volume_level(0.5)
    await master.async_media_play()
    await master.async_media_pause()
    await master.async_media_stop()
    await master.async_media_previous_track()
    await master.async_media_next_track()
    await master.async_media_seek(35)
    await master.async_clear_playlist()
    await master.async_set_shuffle(False)
    # stop player and run more stuff
    get_request_return_values["player"] = SAMPLE_PLAYER_STOPPED
    await master._updater._update(["player"])
    await master.hass.async_block_till_done()
    await master.async_mute_volume(True)
    # now turn off (stopped and all outputs unselected)
    get_request_return_values["outputs"] = SAMPLE_OUTPUTS_UNSELECTED
    await master._updater._update(["outputs"])
    await master.hass.async_block_till_done()
    await master.async_toggle()
    # test media play
    with patch("asyncio.sleep", autospec=True):
        await master.async_play_media(MEDIA_TYPE_MUSIC, "somefile.mp3")
        await master.async_play_media(MEDIA_TYPE_TVSHOW, "wontwork.mp4")

        # throw timeout error in media play
        def timeout_side_effect(coro, timeout=None):
            create_task(coro).cancel()
            raise AsyncioTimeoutError

        with patch("asyncio.wait_for", autospec=True) as wait_for_mock:
            wait_for_mock.side_effect = timeout_side_effect
            await master.async_play_media(MEDIA_TYPE_MUSIC, "somefile.mp3")


async def test_librespot_java_stuff(
    hass, master, config_entry, get_request_return_values
):
    """Test options update and librespot-java stuff."""
    with patch(
        "homeassistant.components.forked_daapd.media_player.LibrespotJavaAPI",
        autospec=True,
    ):
        hass.config_entries.async_update_entry(config_entry, options=OPTIONS_DATA)
        await hass.async_block_till_done()
    get_request_return_values["player"] = SAMPLE_PLAYER_PLAYING
    await master._updater._update(["player"])
    await master.hass.async_block_till_done()
    await master.async_play_media(MEDIA_TYPE_MUSIC, "somefile.mp3")
    await master.async_media_previous_track()
    await master.async_media_next_track()
    await master.async_media_play()


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_config_flow(hass, config_entry):
    """Test that the user step works."""
    with patch(
        "homeassistant.components.forked_daapd.config_flow.ForkedDaapdAPI.test_connection"
    ) as mock_test_connection:
        with patch(
            "homeassistant.components.forked_daapd.media_player.ForkedDaapdAPI.get_request"
        ) as mock_get_request:
            mock_get_request.return_value = Future()
            mock_get_request.return_value.set_result(SAMPLE_CONFIG)
            mock_test_connection.return_value = Future()
            mock_test_connection.return_value.set_result("ok")
            config_data = config_entry.data
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_USER}, data=config_data
            )
            await hass.async_block_till_done()
            assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            assert result["title"] == f"{FD_NAME} server"
            assert result["data"][CONF_HOST] == config_data[CONF_HOST]
            assert result["data"][CONF_PORT] == config_data[CONF_PORT]
            assert result["data"][CONF_PASSWORD] == config_data[CONF_PASSWORD]
            assert (
                result["data"][CONF_DEFAULT_VOLUME] == config_data[CONF_DEFAULT_VOLUME]
            )
            assert result["data"][CONF_NAME] == config_data[CONF_NAME]

            # remove entry
            entry = hass.config_entries.async_entries(domain=DOMAIN)[0]
            await hass.config_entries.async_remove(entry.entry_id)

        # test invalid config data
        mock_test_connection.return_value = Future()
        mock_test_connection.return_value.set_result("websocket_not_enabled")
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=config_data
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_config_flow_zeroconf(hass):
    """Test that the user step works."""
    # test invalid zeroconf entry
    discovery_info = {"host": "127.0.0.1", "port": 23}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )  # doesn't create the entry, tries to show form but gets abort
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "not_forked_daapd"

    # now test valid entry
    discovery_info["properties"] = {
        "mtd-version": 1,
        "Machine Name": "zeroconf_test",
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_options_flow(hass, config_entry, master):
    """Test config flow options."""

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TTS_PAUSE_TIME: 0.05,
            CONF_TTS_VOLUME: 0.8,
            CONF_PIPE_CONTROL: "",
        },
    )


async def test_misc(hass, master, config_entry):
    """Test miscellaneous stuff to get to full coverage."""
    await master._updater._update(["database"])
    await hass.async_block_till_done()
    # make updater with bad config
    await config_entry.async_unload(hass)
    with patch(
        "homeassistant.components.forked_daapd.media_player.ForkedDaapdAPI",
        autospec=True,
    ) as mock_api:

        async def get_request_side_effect(update_type):
            if update_type == "outputs":
                return SAMPLE_OUTPUTS_ON
            if update_type == "player":
                return SAMPLE_PLAYER_PAUSED
            if update_type == "queue":
                return SAMPLE_QUEUE
            if update_type == "config":
                return SAMPLE_CONFIG_NO_WEBSOCKET

        mock_api.return_value.get_request.side_effect = get_request_side_effect
        hass.config_entries._entries.append(config_entry)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
