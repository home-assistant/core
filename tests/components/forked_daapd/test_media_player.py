"""The tests for the forked_daapd media player platform."""
from asynctest.mock import patch
import pytest

from homeassistant.components.forked_daapd.media_player import DOMAIN, ForkedDaapdDevice
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.setup import async_setup_component

from tests.common import mock_coro

IP_ADDRESS = "192.168.1.60"
PORT = 3698


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {MP_DOMAIN: {"platform": DOMAIN, CONF_HOST: IP_ADDRESS, CONF_PORT: PORT}}


@pytest.fixture(name="sample_player")
def sample_player_fixture():
    """Create player fixture."""
    return {
        "state": "pause",
        "repeat": "off",
        "consume": False,
        "shuffle": False,
        "volume": 50,
        "item_id": 269,
        "item_length_ms": 278093,
        "item_progress_ms": 3674,
    }


@pytest.fixture(name="sample_queue")
def sample_queue_fixture():
    """Create queue fixture."""
    return {
        "version": 833,
        "count": 20,
        "items": [
            {
                "id": 12122,
                "position": 0,
                "track_id": 10749,
                "title": "Angels",
                "artist": "The xx",
                "artist_sort": "xx, The",
                "album": "Coexist",
                "album_sort": "Coexist",
                "albumartist": "The xx",
                "albumartist_sort": "xx, The",
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


@pytest.fixture(name="sample_outputs")
def sample_outputs_fixture():
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


@pytest.fixture(name="device")
async def device_fixture(
    hass, sample_config, sample_player, sample_queue, sample_outputs,
):
    """Create device fixture."""

    def get_request_side_effect(update_type):
        if update_type == "player":
            return sample_player
        if update_type == "config":
            return sample_config
        if update_type == "outputs":
            return {"outputs": sample_outputs}
        if update_type == "queue":
            return sample_queue

    with patch(
        "homeassistant.components.forked_daapd.media_player.ForkedDaapdAPI",
        autospec=True,
    ):
        device = ForkedDaapdDevice(async_get_clientsession(hass), "192.168.1.60", 3389)
        device._api.get_request.side_effect = (
            get_request_side_effect  # sorry for touching private
        )
        await device.async_init()
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
        async_get_clientsession(hass), IP_ADDRESS, PORT,
    )


async def test_async_turn_on_with_no_last_outputs(device):
    """Test turning on sends API call with no last_outputs."""
    assert device._last_outputs is None  # sorry for touching private
    await device.async_turn_on()
    assert device._api.set_enabled_outputs.call_count == 1  # sorry for touching private


async def test_async_turn_on_with_last_outputs(device, sample_outputs):
    """Test turning on sends API call."""
    device._last_outputs = sample_outputs  # sorry for touching private
    await device.async_turn_on()
    assert device._api.change_output.call_count == len(
        sample_outputs
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


async def test_bunch_of_stuff_device(device, hass, sample_outputs):
    """Run bunch of stuff."""
    await device.turn_on_output(sample_outputs[0])
    await device.turn_off_output(sample_outputs[0])
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
    # test zone
    for zone in device._zones:  # sorry for touching private
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
