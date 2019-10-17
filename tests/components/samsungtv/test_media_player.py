"""Tests for samsungtv Components."""
import asyncio
from unittest.mock import call, patch

from asynctest import mock

import pytest

from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SUPPORT_TURN_ON,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_URL,
)
from homeassistant.components.samsungtv.const import DOMAIN as STV_DOMAIN
from homeassistant.components.samsungtv.media_player import (
    CONF_TIMEOUT,
    SamsungTVDevice,
    SUPPORT_SAMSUNGTV,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.setup import async_setup_component

from tests.common import MockDependency
from homeassistant.util import dt as dt_util
from datetime import timedelta


ENTITY_ID = "media_player.fake"
MOCK_CONFIG = {
    DOMAIN: {
        "platform": STV_DOMAIN,
        CONF_HOST: "fake",
        CONF_NAME: "fake",
        CONF_PORT: 8001,
        CONF_TIMEOUT: 10,
        CONF_MAC: "fake",
    }
}
WORKING_PARAMETERS = {
    CONF_HOST: "fake",
    CONF_NAME: "fake",
    CONF_PORT: 8001,
    CONF_TIMEOUT: 10,
    CONF_MAC: "fake",
    "uuid": None,
}

MOCK_DISCOVERY = {
    "discovery_info": {"name": "[TV]fake2", "model_name": "fake2", "host": "fake2"}
}


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


async def setup_samsungtv(hass, config):
    """Set up mock Samsung TV."""
    with mock.patch("homeassistant.components.samsungtv.media_player.socket"):
        await async_setup_component(hass, "media_player", config)
        await hass.async_block_till_done()


async def test_setup(hass, samsung_mock, wakeonlan_mock):
    """Test setup of platform."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert hass.states.get(ENTITY_ID)


async def test_setup_discovery(hass, samsung_mock, wakeonlan_mock):
    """Test setup of platform with discovery."""
    await setup_samsungtv(hass, MOCK_DISCOVERY)
    assert hass.states.get("media_player.fake2")


async def test_setup_method_selection():
    """Test of method selection."""
    conf = WORKING_PARAMETERS.copy()
    device = SamsungTVDevice(**conf)
    conf[CONF_PORT] = 8001
    assert device._config[CONF_METHOD] == "websocket"
    conf = WORKING_PARAMETERS.copy()
    conf[CONF_PORT] = 8002
    assert device._config[CONF_METHOD] == "websocket"
    conf = WORKING_PARAMETERS.copy()
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
    device = SamsungTVDevice(**WORKING_PARAMETERS)
    await device.async_update()
    assert STATE_ON == device.state


async def test_update_off(samsung_mock):
    """Testing update tv off."""
    device = SamsungTVDevice(**WORKING_PARAMETERS)
    device._exceptions_class = mock.Mock()
    device._exceptions_class.UnhandledResponse = UnhandledResponse
    device._exceptions_class.AccessDenied = AccessDenied
    device._exceptions_class.ConnectionClosed = ConnectionClosed
    _remote = mock.Mock()
    _remote.control = mock.Mock(side_effect=OSError("Boom"))
    device.get_remote = mock.Mock(return_value=_remote)
    await device.async_update()
    assert STATE_OFF == device.state


async def test_send_key(samsung_mock):
    """Test for send key."""
    device = SamsungTVDevice(**WORKING_PARAMETERS)
    device.send_key("KEY_POWER")
    assert STATE_ON == device.state


async def test_send_key_broken_pipe(samsung_mock):
    """Testing broken pipe Exception."""
    device = SamsungTVDevice(**WORKING_PARAMETERS)
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
    device = SamsungTVDevice(**WORKING_PARAMETERS)
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
    device = SamsungTVDevice(**WORKING_PARAMETERS)
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
    device = SamsungTVDevice(**WORKING_PARAMETERS)
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
    device = SamsungTVDevice(**WORKING_PARAMETERS)
    assert not device._power_off_in_progress()
    device._end_of_power_off = dt_util.utcnow() + timedelta(seconds=15)
    assert device._power_off_in_progress()


async def test_name(samsung_mock):
    """Test for name property."""
    # device = SamsungTVDevice(**WORKING_PARAMETERS)
    # assert "fake" == device.name


async def test_state(samsung_mock):
    """Test for state property."""
    device = SamsungTVDevice(**WORKING_PARAMETERS)
    device._state = STATE_ON
    assert STATE_ON == device.state
    device._state = STATE_OFF
    assert STATE_OFF == device.state


async def test_is_volume_muted(hass, samsung_mock):
    """Test for is_volume_muted property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        True,
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_MEDIA_VOLUME_MUTED]
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
        True,
    )
    assert not hass.states.get(ENTITY_ID).attributes[ATTR_MEDIA_VOLUME_MUTED]


async def test_supported_features(samsung_mock):
    """Test for supported_features property."""
    device = SamsungTVDevice(**WORKING_PARAMETERS)
    device._mac = None
    assert SUPPORT_SAMSUNGTV == device.supported_features
    device._mac = "fake"
    assert SUPPORT_SAMSUNGTV | SUPPORT_TURN_ON == device.supported_features


async def test_turn_off(samsung_mock):
    """Test for turn_off."""
    device = SamsungTVDevice(**WORKING_PARAMETERS)
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
        device = SamsungTVDevice(**WORKING_PARAMETERS)
        device._exceptions_class = mock.Mock()
        _remote = mock.Mock()
        _remote.close = mock.Mock(side_effect=OSError("BOOM"))
        device.get_remote = mock.Mock(return_value=_remote)
        device.turn_off()
        mocked_debug.assert_called_once_with("Could not establish connection.")


async def test_volume_up(hass, samsung_mock):
    """Test for volume_up."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # assert samsungctl.remote_legacy.RemoteLegacy.control.assert_called_once_with("KEY_VOLUP")


async def test_volume_down(hass, samsung_mock):
    """Test for volume_down."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_DOWN, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # assert samsungctl.remote_legacy.RemoteLegacy.control.assert_called_once_with("KEY_VOLDOWN")


async def test_mute_volume(hass, samsung_mock):
    """Test for mute_volume."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        True,
    )
    # assert samsungctl.remote_legacy.RemoteLegacy.control.assert_called_once_with("KEY_MUTE")


async def test_media_play_pause(hass, samsung_mock):
    """Test for media_next_track."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PAUSE, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_PAUSED
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PLAY, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_PLAYING


async def test_media_play(hass, samsung_mock):
    """Test for media_play."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PLAY, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # assert samsungctl.remote_legacy.RemoteLegacy.control.assert_called_once_with("KEY_PLAY")


async def test_media_pause(hass, samsung_mock):
    """Test for media_pause."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PAUSE, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # assert samsungctl.remote_legacy.RemoteLegacy.control.assert_called_once_with("KEY_PAUSE")


async def test_media_next_track(hass, samsung_mock):
    """Test for media_next_track."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_NEXT_TRACK, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # assert samsungctl.remote_legacy.RemoteLegacy.control.assert_called_once_with("KEY_FF")


async def test_media_previous_track(hass, samsung_mock):
    """Test for media_previous_track."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # assert samsungctl.remote_legacy.RemoteLegacy.control.assert_called_once_with("KEY_REWIND")


async def test_turn_on(samsung_mock):
    """Test turn on."""
    device = SamsungTVDevice(**WORKING_PARAMETERS)
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
        device = SamsungTVDevice(**WORKING_PARAMETERS)
        device.hass = hass

        device.send_key = mock.Mock()
        await device.async_play_media(MEDIA_TYPE_CHANNEL, "576")

        exp = [call("KEY_5"), call("KEY_7"), call("KEY_6"), call("KEY_ENTER")]
        assert device.send_key.call_args_list == exp
        assert len(sleeps) == 3


async def test_play_media_invalid_type(samsung_mock):
    """Test for play_media with invalid media type."""
    url = "https://example.com"
    device = SamsungTVDevice(**WORKING_PARAMETERS)
    device.send_key = mock.Mock()
    await device.async_play_media(MEDIA_TYPE_URL, url)
    assert device.send_key.call_count == 0


async def test_play_media_channel_as_string(samsung_mock):
    """Test for play_media with invalid channel as string."""
    url = "https://example.com"
    device = SamsungTVDevice(**WORKING_PARAMETERS)
    device.send_key = mock.Mock()
    await device.async_play_media(MEDIA_TYPE_CHANNEL, url)
    assert device.send_key.call_count == 0


async def test_play_media_channel_as_non_positive(hass, samsung_mock):
    """Test for play_media with invalid channel as non positive integer."""
    device = SamsungTVDevice(**WORKING_PARAMETERS)
    device.send_key = mock.Mock()
    await device.async_play_media(MEDIA_TYPE_CHANNEL, "-4")
    assert device.send_key.call_count == 0

    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_CHANNEL,
            ATTR_MEDIA_CONTENT_ID: "-4",
        },
        True,
    )
    # assert samsungctl.remote_legacy.RemoteLegacy.control.assert_not_called()


async def test_select_source(hass, samsung_mock):
    """Test for select_source."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "HDMI"},
        True,
    )
    # assert samsungctl.remote_legacy.RemoteLegacy.control.assert_called_once_with("KEY_HDMI")


async def test_select_source_invalid_source(hass, samsung_mock):
    """Test for select_source with invalid source."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "INVALID"},
        True,
    )
    # assert samsungctl.remote_legacy.RemoteLegacy.control.assert_not_called()
