"""Tests for samsungtv Components."""
import asyncio
from unittest.mock import call, patch

from asynctest import mock

import pytest

from homeassistant.components.media_player.const import (
    SUPPORT_TURN_ON,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_URL,
)
from homeassistant.components.samsungtv.media_player import (
    async_setup_platform,
    CONF_TIMEOUT,
    SamsungTVDevice,
    SUPPORT_SAMSUNGTV,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    STATE_ON,
    CONF_MAC,
    STATE_OFF,
)
from tests.common import MockDependency
from homeassistant.util import dt as dt_util
from datetime import timedelta


WORKING_CONFIG = {
    CONF_HOST: "fake",
    CONF_NAME: "fake",
    CONF_PORT: 8001,
    CONF_TIMEOUT: 10,
    CONF_MAC: "fake",
    "uuid": None,
}

DISCOVERY_INFO = {"name": "fake", "model_name": "fake", "host": "fake"}


class AccessDenied(Exception):
    """Dummy Exception."""


class ConnectionClosed(Exception):
    """Dummy Exception."""


class UnhandledResponse(Exception):
    """Dummy Exception."""


@pytest.fixture
def samsung_mock():
    """Mock samsungctl."""
    with MockDependency("samsungctl"):
        yield


@pytest.fixture
def wakeonlan_mock():
    """Mock wakeonlan."""
    with MockDependency("wakeonlan"):
        yield


async def test_setup(hass, samsung_mock, wakeonlan_mock):
    """Test setup of platform."""
    with mock.patch("homeassistant.components.samsungtv.media_player.socket"):
        add_entities = mock.Mock()
        await async_setup_platform(hass, WORKING_CONFIG, add_entities)


async def test_setup_discovery(hass, samsung_mock, wakeonlan_mock):
    """Test setup of platform with discovery."""
    with mock.patch("homeassistant.components.samsungtv.media_player.socket"):
        add_entities = mock.Mock()
        await async_setup_platform(
            hass, {}, add_entities, discovery_info=DISCOVERY_INFO
        )


async def test_setup_none(hass, samsung_mock, wakeonlan_mock):
    """Test setup of platform with no data."""
    with mock.patch("homeassistant.components.samsungtv.media_player.socket"):
        with patch(
            "homeassistant.components.samsungtv.media_player.LOGGER.warning"
        ) as mocked_warn:
            add_entities = mock.Mock()
            await async_setup_platform(hass, {}, add_entities, discovery_info=None)
            mocked_warn.assert_called_once_with("Cannot determine device")
            add_entities.assert_not_called()


async def test_setup_method_selection():
    """Test of method selection."""
    conf = WORKING_CONFIG.copy()
    device = SamsungTVDevice(**conf)
    conf[CONF_PORT] = 8001
    assert device._config[CONF_METHOD] == "websocket"
    conf = WORKING_CONFIG.copy()
    conf[CONF_PORT] = 8002
    assert device._config[CONF_METHOD] == "websocket"
    conf = WORKING_CONFIG.copy()
    conf[CONF_PORT] = 55000
    device = SamsungTVDevice(**conf)
    assert device._config[CONF_METHOD] == "legacy"
    conf[CONF_PORT] = 12345
    device = SamsungTVDevice(**conf)
    assert device._config[CONF_METHOD] is None
    conf[CONF_PORT] = None
    device = SamsungTVDevice(**conf)
    assert device._config[CONF_METHOD] is None


async def test_update_on(samsung_mock):
    """Testing update tv on."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.update()
    assert STATE_ON == device.state


async def test_update_off(samsung_mock):
    """Testing update tv off."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device._exceptions_class = mock.Mock()
    device._exceptions_class.UnhandledResponse = UnhandledResponse
    device._exceptions_class.AccessDenied = AccessDenied
    device._exceptions_class.ConnectionClosed = ConnectionClosed
    _remote = mock.Mock()
    _remote.control = mock.Mock(side_effect=OSError("Boom"))
    device.get_remote = mock.Mock(return_value=_remote)
    device.update()
    assert STATE_OFF == device.state


async def test_send_key(samsung_mock):
    """Test for send key."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key("KEY_POWER")
    assert STATE_ON == device.state


async def test_send_key_broken_pipe(samsung_mock):
    """Testing broken pipe Exception."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device._exceptions_class = mock.Mock()
    device._exceptions_class.UnhandledResponse = UnhandledResponse
    device._exceptions_class.AccessDenied = AccessDenied
    device._exceptions_class.ConnectionClosed = ConnectionClosed
    _remote = mock.Mock()
    _remote.control = mock.Mock(side_effect=BrokenPipeError("Boom"))
    device.get_remote = mock.Mock(return_value=_remote)
    device.send_key("HELLO")
    assert device._remote is None
    assert STATE_ON == device.state


async def test_send_key_connection_closed_retry_succeed(samsung_mock):
    """Test retry on connection closed."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device._exceptions_class = mock.Mock()
    device._exceptions_class.UnhandledResponse = UnhandledResponse
    device._exceptions_class.AccessDenied = AccessDenied
    device._exceptions_class.ConnectionClosed = ConnectionClosed
    _remote = mock.Mock()
    _remote.control = mock.Mock(
        side_effect=[device._exceptions_class.ConnectionClosed("Boom"), mock.DEFAULT]
    )
    device.get_remote = mock.Mock(return_value=_remote)
    command = "HELLO"
    device.send_key(command)
    assert STATE_ON == device.state
    # verify that _remote.control() get called twice because of retry logic
    expected = [mock.call(command), mock.call(command)]
    assert expected == _remote.control.call_args_list


async def test_send_key_unhandled_response(samsung_mock):
    """Testing unhandled response exception."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    _remote = mock.Mock()
    _remote.control = mock.Mock(
        side_effect=device._exceptions_class.UnhandledResponse("Boom")
    )
    device.get_remote = mock.Mock(return_value=_remote)
    device.send_key("HELLO")
    assert device._remote is None
    assert STATE_ON == device.state


async def test_send_key_os_error(samsung_mock):
    """Testing broken pipe Exception."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device._exceptions_class = mock.Mock()
    device._exceptions_class.UnhandledResponse = UnhandledResponse
    device._exceptions_class.AccessDenied = AccessDenied
    device._exceptions_class.ConnectionClosed = ConnectionClosed
    _remote = mock.Mock()
    _remote.control = mock.Mock(side_effect=OSError("Boom"))
    device.get_remote = mock.Mock(return_value=_remote)
    device.send_key("HELLO")
    assert device._remote is None
    assert STATE_OFF == device.state


async def test_power_off_in_progress(samsung_mock):
    """Test for power_off_in_progress."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    assert not device._power_off_in_progress()
    device._end_of_power_off = dt_util.utcnow() + timedelta(seconds=15)
    assert device._power_off_in_progress()


async def test_name(samsung_mock):
    """Test for name property."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    assert "fake" == device.name


async def test_state(samsung_mock):
    """Test for state property."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device._state = STATE_ON
    assert STATE_ON == device.state
    device._state = STATE_OFF
    assert STATE_OFF == device.state


async def test_is_volume_muted(samsung_mock):
    """Test for is_volume_muted property."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device._muted = False
    assert not device.is_volume_muted
    device._muted = True
    assert device.is_volume_muted


async def test_supported_features(samsung_mock):
    """Test for supported_features property."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device._mac = None
    assert SUPPORT_SAMSUNGTV == device.supported_features
    device._mac = "fake"
    assert SUPPORT_SAMSUNGTV | SUPPORT_TURN_ON == device.supported_features


async def test_turn_off(samsung_mock):
    """Test for turn_off."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    _remote = mock.Mock()
    _remote.close = mock.Mock()
    device._end_of_power_off = None
    device.turn_off()
    assert device._end_of_power_off is not None
    device.send_key.assert_called_once_with("KEY_POWER")
    device.send_key = mock.Mock()
    device._config["method"] = "legacy"
    device.turn_off()
    device.send_key.assert_called_once_with("KEY_POWEROFF")


async def test_turn_off_os_error():
    """Test for turn_off with OSError."""
    with patch(
        "homeassistant.components.samsungtv.media_player.LOGGER.debug"
    ) as mocked_debug:
        device = SamsungTVDevice(**WORKING_CONFIG)
        device._exceptions_class = mock.Mock()
        _remote = mock.Mock()
        _remote.close = mock.Mock(side_effect=OSError("BOOM"))
        device.get_remote = mock.Mock(return_value=_remote)
        device.turn_off()
        mocked_debug.assert_called_once_with("Could not establish connection.")


async def test_volume_up(samsung_mock):
    """Test for volume_up."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    device.volume_up()
    device.send_key.assert_called_once_with("KEY_VOLUP")


async def test_volume_down(samsung_mock):
    """Test for volume_down."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    device.volume_down()
    device.send_key.assert_called_once_with("KEY_VOLDOWN")


async def test_mute_volume(samsung_mock):
    """Test for mute_volume."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    device.mute_volume(True)
    device.send_key.assert_called_once_with("KEY_MUTE")


async def test_media_play_pause(samsung_mock):
    """Test for media_next_track."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    device._playing = False
    device.media_play_pause()
    device.send_key.assert_called_once_with("KEY_PLAY")
    assert device._playing
    device.send_key = mock.Mock()
    device.media_play_pause()
    device.send_key.assert_called_once_with("KEY_PAUSE")
    assert not device._playing


async def test_media_play(samsung_mock):
    """Test for media_play."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    device._playing = False
    device.media_play()
    device.send_key.assert_called_once_with("KEY_PLAY")
    assert device._playing


async def test_media_pause(samsung_mock):
    """Test for media_pause."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    device._playing = True
    device.media_pause()
    device.send_key.assert_called_once_with("KEY_PAUSE")
    assert not device._playing


async def test_media_next_track(samsung_mock):
    """Test for media_next_track."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    device.media_next_track()
    device.send_key.assert_called_once_with("KEY_FF")


async def test_media_previous_track(samsung_mock):
    """Test for media_previous_track."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    device.media_previous_track()
    device.send_key.assert_called_once_with("KEY_REWIND")


async def test_turn_on(samsung_mock):
    """Test turn on."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    device._mac = None
    device.turn_on()
    device.send_key.assert_called_once_with("KEY_POWERON")
    device._wol.send_magic_packet = mock.Mock()
    device._mac = "fake"
    device.turn_on()
    device._wol.send_magic_packet.assert_called_once_with("fake")


async def test_play_media(hass, samsung_mock):
    """Test for play_media."""
    asyncio_sleep = asyncio.sleep
    sleeps = []

    async def sleep(duration, loop):
        sleeps.append(duration)
        await asyncio_sleep(0, loop=loop)

    with patch("asyncio.sleep", new=sleep):
        device = SamsungTVDevice(**WORKING_CONFIG)
        device.hass = hass

        device.send_key = mock.Mock()
        await device.async_play_media(MEDIA_TYPE_CHANNEL, "576")

        exp = [call("KEY_5"), call("KEY_7"), call("KEY_6"), call("KEY_ENTER")]
        assert device.send_key.call_args_list == exp
        assert len(sleeps) == 3


async def test_play_media_invalid_type(samsung_mock):
    """Test for play_media with invalid media type."""
    url = "https://example.com"
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    await device.async_play_media(MEDIA_TYPE_URL, url)
    assert device.send_key.call_count == 0


async def test_play_media_channel_as_string(samsung_mock):
    """Test for play_media with invalid channel as string."""
    url = "https://example.com"
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    await device.async_play_media(MEDIA_TYPE_CHANNEL, url)
    assert device.send_key.call_count == 0


async def test_play_media_channel_as_non_positive(samsung_mock):
    """Test for play_media with invalid channel as non positive integer."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    await device.async_play_media(MEDIA_TYPE_CHANNEL, "-4")
    assert device.send_key.call_count == 0


async def test_select_source(hass, samsung_mock):
    """Test for select_source."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.hass = hass
    device.send_key = mock.Mock()
    await device.async_select_source("HDMI")
    exp = [call("KEY_HDMI")]
    assert device.send_key.call_args_list == exp


async def test_select_source_invalid_source(samsung_mock):
    """Test for select_source with invalid source."""
    device = SamsungTVDevice(**WORKING_CONFIG)
    device.send_key = mock.Mock()
    await device.async_select_source("INVALID")
    assert device.send_key.call_count == 0
