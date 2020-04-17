"""The tests for the forked_daapd media player platform."""
from asyncio import Future

from aiohttp import ClientResponse, ClientResponseError, ClientSession
from asynctest.mock import MagicMock, patch
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.forked_daapd.const import (
    CONF_DEFAULT_VOLUME,
    CONF_PIPE_CONTROL,
    CONF_PIPE_CONTROL_PORT,
    CONF_TTS_PAUSE_TIME,
    CONF_TTS_VOLUME,
    DOMAIN,
    FD_NAME,
)
from homeassistant.components.forked_daapd.media_player import ForkedDaapdDevice
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_TVSHOW,
)
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.setup import async_setup_component

from tests.common import mock_coro

IP_ADDRESS = "192.168.1.60"
PORT = 3698
CONFIG = {
    CONF_HOST: IP_ADDRESS,
    CONF_PORT: PORT,
    CONF_PASSWORD: "",
    CONF_DEFAULT_VOLUME: 0.5,
    CONF_NAME: "Test Server",
}


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {MP_DOMAIN: {"platform": DOMAIN, CONF_HOST: IP_ADDRESS, CONF_PORT: PORT}}


@pytest.fixture(name="sample_player_paused")
def sample_player_paused_fixture():
    """Create player fixture."""
    return {
        "state": "pause",
        "repeat": "off",
        "consume": False,
        "shuffle": False,
        "volume": 0,
        "item_id": 12322,
        "item_length_ms": 50,
        "item_progress_ms": 5,
    }


@pytest.fixture(name="sample_player_playing")
def sample_player_playing_fixture():
    """Create player fixture."""
    return {
        "state": "play",
        "repeat": "off",
        "consume": False,
        "shuffle": False,
        "volume": 50,
        "item_id": 12322,
        "item_length_ms": 50,
        "item_progress_ms": 5,
    }


@pytest.fixture(name="sample_player_stop")
def sample_player_stop_fixture():
    """Create player fixture."""
    return {
        "state": "stop",
        "repeat": "off",
        "consume": False,
        "shuffle": False,
        "volume": 50,
        "item_id": 12322,
        "item_length_ms": 50,
        "item_progress_ms": 5,
    }


@pytest.fixture(name="sample_queue")
def sample_queue_fixture():
    """Create queue fixture."""
    return {
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


@pytest.fixture(name="sample_tts_queue")
def sample_tts_queue_fixture():
    """Create queue fixture."""
    return {
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
            },
        ],
    }


@pytest.fixture(name="sample_config")
def sample_config_fixture():
    """Create outputs fixture."""
    return {
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


@pytest.fixture(name="sample_outputs_on")
def sample_outputs_on_fixture():
    """Create outputs fixture."""
    return [
        {
            "id": "123456789012345",
            "name": "kitchen",
            "type": "AirPlay",
            "selected": True,
            "has_password": False,
            "requires_auth": False,
            "needs_auth_key": False,
            "volume": 0,
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
    ]


@pytest.fixture(name="sample_outputs_off")
def sample_outputs_off_fixture():
    """Create outputs fixture."""
    return [
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


@pytest.fixture(name="device")
async def device_fixture(
    hass,
    sample_config,
    sample_player_paused,
    sample_queue,
    sample_outputs_on,
    sample_tts_queue,
):
    """Create device fixture."""
    # queue_iter = itertools.cycle([sample_queue, sample_tts_queue])
    # sample_player = [sample_player_paused, sample_player_playing]
    # sample_outputs = [sample_outputs_on, sample_outputs_off]

    async def get_request_side_effect(update_type):
        if update_type == "player":
            return sample_player_paused
        if update_type == "config":
            return sample_config
        if update_type == "outputs":
            return {"outputs": sample_outputs_on}
        if update_type == "queue":
            return sample_tts_queue

    def async_add_entities(list_of_entities, update_on_add):
        for entity in list_of_entities:
            print(entity)
        print(update_on_add, "Update on add: {update_on_add}")

    async def add_to_queue_side_effect(uris, playback, playback_from_position=None):
        await device._update_queue()  # sorry for touching private
        await device._update_player()  # sorry for touching private

    with patch(
        "homeassistant.components.forked_daapd.media_player.ForkedDaapdAPI",
        autospec=True,
    ):
        device = ForkedDaapdDevice(
            hass,
            "Friendly Name",
            "192.168.1.60",
            3389,
            "password",
            0.5,
            async_add_entities,
        )
        device._api.get_request.side_effect = (
            get_request_side_effect  # sorry for touching private
        )
        device._api.add_to_queue.side_effect = add_to_queue_side_effect
        await device.async_init()
        await device._update_queue()  # sorry for touching private
    return device


async def test_configuring_forked_daapd_creates_entry(hass, config):
    """Test that specifying config will create an entry."""
    with patch(
        "homeassistant.components.forked_daapd.media_player.async_setup_platform",
        return_value=mock_coro(True),
    ) as mock_setup:
        await async_setup_component(hass, MP_DOMAIN, config)
        await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1


async def test_not_configuring_forked_daapd_not_creates_entry(hass):
    """Test that no config will not create an entry."""
    with patch(
        "homeassistant.components.forked_daapd.media_player.async_setup_platform",
        return_value=mock_coro(True),
    ) as mock_setup:
        await async_setup_component(hass, MP_DOMAIN, {})
        await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 0


async def test_configuring_forked_daapd_sets_host_and_port(hass, config):
    """Test that specifying config will create an entry."""
    with patch(
        "homeassistant.components.forked_daapd.media_player.ForkedDaapdAPI",
        autospec=True,
    ) as local_mock_api:
        await async_setup_component(hass, MP_DOMAIN, config)
        await hass.async_block_till_done()
    local_mock_api.assert_called_with(
        async_get_clientsession(hass), IP_ADDRESS, PORT, None
    )


async def test_async_turn_on_with_no_last_outputs(device):
    """Test turning on sends API call with no last_outputs."""
    assert device._last_outputs is None  # sorry for touching private
    await device.async_turn_on()
    assert device._api.set_enabled_outputs.call_count == 1  # sorry for touching private


async def test_async_turn_on_with_last_outputs(device, sample_outputs_on):
    """Test turning on sends API call."""
    device._last_outputs = sample_outputs_on  # sorry for touching private
    await device.async_turn_on()
    assert device._api.change_output.call_count == len(
        sample_outputs_on
    )  # sorry for touching private


async def test_update_player(device, hass):
    """Test update_callback makes api calls."""
    with patch(
        "homeassistant.components.media_player.MediaPlayerDevice.async_schedule_update_ha_state"
    ):
        await device.update_callback(["player", "config", "volume", "options", "queue"])
    device._api.get_request.assert_any_call(
        endpoint="player"
    )  # sorry for touching private
    device._api.get_request.assert_any_call(
        endpoint="queue"
    )  # sorry for touching private
    device._api.get_request.assert_any_call(
        endpoint="config"
    )  # sorry for touching private
    device._api.get_request.assert_any_call(
        endpoint="outputs"
    )  # sorry for touching private


async def test_bunch_of_stuff_device(
    device, hass, sample_outputs_off, sample_player_playing, sample_player_stop
):
    """Run bunch of stuff."""
    await device.turn_on_output(sample_outputs_off[0])
    await device.turn_off_output(sample_outputs_off[0])
    await device.async_turn_on()
    await device.async_turn_off()
    await device.async_toggle()
    await device.async_mute_volume(True)
    await device.async_mute_volume(False)
    await device.async_set_volume_level(0.5)
    await device.async_media_play()
    await device.async_media_pause()
    await device.async_media_stop()
    await device.async_media_previous_track()
    await device.async_media_next_track()
    await device.async_media_seek(35)
    await device.async_clear_playlist()
    await device.async_set_shuffle(False)
    print(device.should_poll)
    print(device.supported_features)
    print(device.name)
    print(device.state)
    print(device.volume_level)
    print(device.is_volume_muted)
    print(device.media_content_id)
    print(device.media_content_type)
    print(device.media_duration)
    print(device.media_position)
    print(device.media_position_updated_at)
    print(device.media_title)
    print(device.media_artist)
    print(device.media_album_name)
    print(device.media_album_artist)
    print(device.media_track)
    print(device.shuffle)
    print(device.unique_id)
    print(device.media_image_url)
    # test zone
    for zone in device._zones.values():  # sorry for touching private
        await zone.async_turn_on()
        await zone.async_turn_off()
        await zone.async_toggle()
        await zone.async_set_volume_level(0.3)
        await zone.async_mute_volume(True)
        await zone.async_mute_volume(False)
        print(zone.should_poll)
        print(zone.supported_features)
        print(zone.name)
        print(zone.state)
        print(zone.volume_level)
        print(zone.is_volume_muted)
        print(zone.unique_id)
    # test media play
    await device.async_play_media(MEDIA_TYPE_MUSIC, "somefile.mp3")
    await device.async_play_media(MEDIA_TYPE_TVSHOW, "wontwork.mp4")
    # stop player and run more stuff
    device._data.player = sample_player_stop
    device._update_track_info()  # have to update track info after manual player or queue update
    print(device.state)
    await device.async_mute_volume(True)
    # change device to off state (stopped/paused and outputs off) and run more
    device._data.outputs = sample_outputs_off
    print(device.output_volume_level(-1))  # invalid output


async def test_librespot_java_stuff(
    device, hass, sample_outputs_off, sample_player_playing
):
    """Test config stuff."""
    device.update_options(options={CONF_PIPE_CONTROL: ""})
    with patch(
        "homeassistant.components.forked_daapd.media_player.LibrespotJavaAPI",
        autospec=True,
    ):
        device.update_options(
            options={
                CONF_PIPE_CONTROL: "librespot-java",
                CONF_PIPE_CONTROL_PORT: "123",
                CONF_TTS_PAUSE_TIME: 0.5,
                CONF_TTS_VOLUME: 0.25,
            }
        )
    device._data.player = sample_player_playing
    device._update_track_info()  # have to update track info after manual player or queue update
    await device.async_play_media(MEDIA_TYPE_MUSIC, "somefile.mp3")
    await device.async_media_previous_track()
    await device.async_media_next_track()
    await device.async_media_play()


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_config_entry(hass):
    """Test that the user step works."""

    with patch(
        "homeassistant.components.forked_daapd.config_flow.async_get_clientsession",
        autospec=True,
    ) as mock_async_get_clientsession:
        mock_clientresponse = MagicMock(spec=ClientResponse)
        mock_clientresponse.json.return_value = Future()
        mock_clientresponse.json.return_value.set_result({"websocket_port": 55})

        context_manager = MagicMock()
        context_manager.__aenter__.return_value = mock_clientresponse

        mock_clientsession = MagicMock(spec=ClientSession)
        mock_clientsession.get.return_value = context_manager

        mock_async_get_clientsession.return_value = mock_clientsession

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )
    assert result["title"] == f"{FD_NAME} server"
    assert result["data"][CONF_HOST] == CONFIG[CONF_HOST]
    assert result["data"][CONF_PORT] == CONFIG[CONF_PORT]
    assert result["data"][CONF_PASSWORD] == CONFIG[CONF_PASSWORD]
    assert result["data"][CONF_DEFAULT_VOLUME] == CONFIG[CONF_DEFAULT_VOLUME]
    assert result["data"][CONF_NAME] == CONFIG[CONF_NAME]

    # remove entry
    entry = hass.config_entries.async_entries(domain=DOMAIN)[0]
    await hass.config_entries.async_remove(entry.entry_id)

    # test error entry
    def raise_error():
        raise ClientResponseError

    mock_clientresponse.json.side_effect = raise_error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    # test zeroconf entry
    discovery_info = {
        "properties": {"mtd-version": 1, "Machine Name": "zeroconf_test"},
        "host": "127.0.0.1",
        "port": 23,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )  # doesn't create the entry, tries to show form but gets abort

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
