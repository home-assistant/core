"""Tests for samsungtv component."""
import asyncio
from datetime import timedelta
import logging

from asynctest import mock
from asynctest.mock import call, patch
import pytest
from samsungctl import exceptions
from websocket import WebSocketException

from homeassistant.components.media_player import DEVICE_CLASS_TV
from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_URL,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SUPPORT_TURN_ON,
)
from homeassistant.components.samsungtv.const import (
    CONF_ON_ACTION,
    DOMAIN as SAMSUNGTV_DOMAIN,
)
from homeassistant.components.samsungtv.media_player import SUPPORT_SAMSUNGTV
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.fake"
MOCK_CONFIG = {
    SAMSUNGTV_DOMAIN: [
        {
            CONF_HOST: "fake",
            CONF_NAME: "fake",
            CONF_PORT: 8001,
            CONF_ON_ACTION: [{"delay": "00:00:01"}],
        }
    ]
}

ENTITY_ID_NOTURNON = f"{DOMAIN}.fake_noturnon"
MOCK_CONFIG_NOTURNON = {
    SAMSUNGTV_DOMAIN: [
        {CONF_HOST: "fake_noturnon", CONF_NAME: "fake_noturnon", CONF_PORT: 55000}
    ]
}


@pytest.fixture(name="remote")
def remote_fixture():
    """Patch the samsungctl Remote."""
    with patch("homeassistant.components.samsungtv.config_flow.Remote"), patch(
        "homeassistant.components.samsungtv.config_flow.socket"
    ) as socket1, patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote"
    ) as remote_class, patch(
        "homeassistant.components.samsungtv.socket"
    ) as socket2:
        remote = mock.Mock()
        remote_class.return_value = remote
        socket1.gethostbyname.return_value = "FAKE_IP_ADDRESS"
        socket2.gethostbyname.return_value = "FAKE_IP_ADDRESS"
        yield remote


@pytest.fixture(name="delay")
def delay_fixture():
    """Patch the delay script function."""
    with patch(
        "homeassistant.components.samsungtv.media_player.Script.async_run"
    ) as delay:
        yield delay


@pytest.fixture
def mock_now():
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


async def setup_samsungtv(hass, config):
    """Set up mock Samsung TV."""
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, config)
    await hass.async_block_till_done()


async def test_setup_with_turnon(hass, remote):
    """Test setup of platform."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert hass.states.get(ENTITY_ID)


async def test_setup_without_turnon(hass, remote):
    """Test setup of platform."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOTURNON)
    assert hass.states.get(ENTITY_ID_NOTURNON)


async def test_update_on(hass, remote, mock_now):
    """Testing update tv on."""
    await setup_samsungtv(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_update_off(hass, remote, mock_now):
    """Testing update tv off."""
    await setup_samsungtv(hass, MOCK_CONFIG)

    with patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote",
        side_effect=[OSError("Boom"), mock.DEFAULT],
    ):

        next_update = mock_now + timedelta(minutes=5)
        with patch("homeassistant.util.dt.utcnow", return_value=next_update):
            async_fire_time_changed(hass, next_update)
            await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_OFF


async def test_update_access_denied(hass, remote, mock_now):
    """Testing update tv unhandled response exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)

    with patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote",
        side_effect=exceptions.AccessDenied("Boom"),
    ):

        next_update = mock_now + timedelta(minutes=5)
        with patch("homeassistant.util.dt.utcnow", return_value=next_update):
            async_fire_time_changed(hass, next_update)
            await hass.async_block_till_done()

    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]


async def test_update_unhandled_response(hass, remote, mock_now):
    """Testing update tv unhandled response exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)

    with patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote",
        side_effect=[exceptions.UnhandledResponse("Boom"), mock.DEFAULT],
    ):

        next_update = mock_now + timedelta(minutes=5)
        with patch("homeassistant.util.dt.utcnow", return_value=next_update):
            async_fire_time_changed(hass, next_update)
            await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_ON


async def test_send_key(hass, remote):
    """Test for send key."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    # key and update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_VOLUP")]
    assert remote.close.call_count == 1
    assert remote.close.call_args_list == [call()]
    assert state.state == STATE_ON


async def test_send_key_broken_pipe(hass, remote):
    """Testing broken pipe Exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.control = mock.Mock(side_effect=BrokenPipeError("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_send_key_connection_closed_retry_succeed(hass, remote):
    """Test retry on connection closed."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.control = mock.Mock(
        side_effect=[exceptions.ConnectionClosed("Boom"), mock.DEFAULT, mock.DEFAULT]
    )
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    # key because of retry two times and update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [
        call("KEY_VOLUP"),
        call("KEY_VOLUP"),
    ]
    assert remote.close.call_count == 1
    assert remote.close.call_args_list == [call()]
    assert state.state == STATE_ON


async def test_send_key_unhandled_response(hass, remote):
    """Testing unhandled response exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.control = mock.Mock(side_effect=exceptions.UnhandledResponse("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_send_key_websocketexception(hass, remote):
    """Testing unhandled response exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.control = mock.Mock(side_effect=WebSocketException("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_send_key_os_error(hass, remote):
    """Testing broken pipe Exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.control = mock.Mock(side_effect=OSError("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_name(hass, remote):
    """Test for name property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake"


async def test_state_with_turnon(hass, remote, delay):
    """Test for state property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert delay.call_count == 1

    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_state_without_turnon(hass, remote):
    """Test for state property."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOTURNON)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID_NOTURNON}, True
    )
    state = hass.states.get(ENTITY_ID_NOTURNON)
    assert state.state == STATE_ON
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID_NOTURNON}, True
    )
    state = hass.states.get(ENTITY_ID_NOTURNON)
    assert state.state == STATE_OFF


async def test_supported_features_with_turnon(hass, remote):
    """Test for supported_features property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_SAMSUNGTV | SUPPORT_TURN_ON
    )


async def test_supported_features_without_turnon(hass, remote):
    """Test for supported_features property."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOTURNON)
    state = hass.states.get(ENTITY_ID_NOTURNON)
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_SAMSUNGTV


async def test_device_class(hass, remote):
    """Test for device_class property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_TV


async def test_turn_off_websocket(hass, remote):
    """Test for turn_off."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_POWER")]


async def test_turn_off_legacy(hass):
    """Test for turn_off."""
    with patch("homeassistant.components.samsungtv.config_flow.socket"), patch(
        "homeassistant.components.samsungtv.config_flow.Remote",
        side_effect=[OSError("Boom"), mock.DEFAULT],
    ), patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote"
    ) as remote_class, patch(
        "homeassistant.components.samsungtv.socket"
    ):
        remote = mock.Mock()
        remote_class.return_value = remote
        await setup_samsungtv(hass, MOCK_CONFIG_NOTURNON)
        assert await hass.services.async_call(
            DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID_NOTURNON}, True
        )
        # key called
        assert remote.control.call_count == 1
        assert remote.control.call_args_list == [call("KEY_POWEROFF")]


async def test_turn_off_os_error(hass, remote, caplog):
    """Test for turn_off with OSError."""
    caplog.set_level(logging.DEBUG)
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.close = mock.Mock(side_effect=OSError("BOOM"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert "Could not establish connection." in caplog.text


async def test_volume_up(hass, remote):
    """Test for volume_up."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_VOLUP")]
    assert remote.close.call_count == 1
    assert remote.close.call_args_list == [call()]


async def test_volume_down(hass, remote):
    """Test for volume_down."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_DOWN, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_VOLDOWN")]
    assert remote.close.call_count == 1
    assert remote.close.call_args_list == [call()]


async def test_mute_volume(hass, remote):
    """Test for mute_volume."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        True,
    )
    # key and update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_MUTE")]
    assert remote.close.call_count == 1
    assert remote.close.call_args_list == [call()]


async def test_media_play(hass, remote):
    """Test for media_play."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PLAY, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_PLAY")]
    assert remote.close.call_count == 1
    assert remote.close.call_args_list == [call()]


async def test_media_pause(hass, remote):
    """Test for media_pause."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PAUSE, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_PAUSE")]
    assert remote.close.call_count == 1
    assert remote.close.call_args_list == [call()]


async def test_media_next_track(hass, remote):
    """Test for media_next_track."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_NEXT_TRACK, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_CHUP")]
    assert remote.close.call_count == 1
    assert remote.close.call_args_list == [call()]


async def test_media_previous_track(hass, remote):
    """Test for media_previous_track."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_CHDOWN")]
    assert remote.close.call_count == 1
    assert remote.close.call_args_list == [call()]


async def test_turn_on_with_turnon(hass, remote, delay):
    """Test turn on."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert delay.call_count == 1


async def test_turn_on_without_turnon(hass, remote):
    """Test turn on."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOTURNON)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID_NOTURNON}, True
    )
    # nothing called as not supported feature
    assert remote.control.call_count == 0


async def test_play_media(hass, remote):
    """Test for play_media."""
    asyncio_sleep = asyncio.sleep
    sleeps = []

    async def sleep(duration, loop):
        sleeps.append(duration)
        await asyncio_sleep(0, loop=loop)

    await setup_samsungtv(hass, MOCK_CONFIG)
    with patch("asyncio.sleep", new=sleep):
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_CHANNEL,
                ATTR_MEDIA_CONTENT_ID: "576",
            },
            True,
        )
        # keys and update called
        assert remote.control.call_count == 4
        assert remote.control.call_args_list == [
            call("KEY_5"),
            call("KEY_7"),
            call("KEY_6"),
            call("KEY_ENTER"),
        ]
        assert remote.close.call_count == 1
        assert remote.close.call_args_list == [call()]
        assert len(sleeps) == 3


async def test_play_media_invalid_type(hass, remote):
    """Test for play_media with invalid media type."""
    with patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote"
    ) as remote, patch("homeassistant.components.samsungtv.config_flow.socket"):
        url = "https://example.com"
        await setup_samsungtv(hass, MOCK_CONFIG)
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_URL,
                ATTR_MEDIA_CONTENT_ID: url,
            },
            True,
        )
        # only update called
        assert remote.control.call_count == 0
        assert remote.close.call_count == 0
        assert remote.call_count == 1


async def test_play_media_channel_as_string(hass, remote):
    """Test for play_media with invalid channel as string."""
    with patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote"
    ) as remote, patch("homeassistant.components.samsungtv.config_flow.socket"):
        url = "https://example.com"
        await setup_samsungtv(hass, MOCK_CONFIG)
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_CHANNEL,
                ATTR_MEDIA_CONTENT_ID: url,
            },
            True,
        )
        # only update called
        assert remote.control.call_count == 0
        assert remote.close.call_count == 0
        assert remote.call_count == 1


async def test_play_media_channel_as_non_positive(hass, remote):
    """Test for play_media with invalid channel as non positive integer."""
    with patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote"
    ) as remote, patch("homeassistant.components.samsungtv.config_flow.socket"):
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
        # only update called
        assert remote.control.call_count == 0
        assert remote.close.call_count == 0
        assert remote.call_count == 1


async def test_select_source(hass, remote):
    """Test for select_source."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "HDMI"},
        True,
    )
    # key and update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_HDMI")]
    assert remote.close.call_count == 1
    assert remote.close.call_args_list == [call()]


async def test_select_source_invalid_source(hass, remote):
    """Test for select_source with invalid source."""
    with patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote"
    ) as remote, patch("homeassistant.components.samsungtv.config_flow.socket"):
        await setup_samsungtv(hass, MOCK_CONFIG)
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "INVALID"},
            True,
        )
        # only update called
        assert remote.control.call_count == 0
        assert remote.close.call_count == 0
        assert remote.call_count == 1
