"""Tests for samsungtv component."""
import asyncio
from datetime import timedelta
import logging
from unittest.mock import DEFAULT as DEFAULT_MOCK, Mock, PropertyMock, call, patch

import pytest
from samsungctl import exceptions
from samsungtvws.exceptions import ConnectionFailure
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
    CONF_IP_ADDRESS,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
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
    STATE_UNAVAILABLE,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.fake"
MOCK_CONFIG = {
    SAMSUNGTV_DOMAIN: [
        {
            CONF_HOST: "fake",
            CONF_NAME: "fake",
            CONF_PORT: 55000,
            CONF_ON_ACTION: [{"delay": "00:00:01"}],
        }
    ]
}
MOCK_CONFIGWS = {
    SAMSUNGTV_DOMAIN: [
        {
            CONF_HOST: "fake",
            CONF_NAME: "fake",
            CONF_PORT: 8001,
            CONF_TOKEN: "123456789",
            CONF_ON_ACTION: [{"delay": "00:00:01"}],
        }
    ]
}
MOCK_CALLS_WS = {
    "host": "fake",
    "port": 8002,
    "token": None,
    "timeout": 31,
    "name": "HomeAssistant",
}
MOCK_CALLS_DEVICEINFO = {
    "host": "fake",
    "port": 8002,
    "token": "987654321",
    "timeout": 8,
    "name": "HomeAssistant",
}

MOCK_ENTRY_WS = {
    CONF_IP_ADDRESS: "test",
    CONF_HOST: "fake",
    CONF_METHOD: "websocket",
    CONF_NAME: "fake",
    CONF_PORT: 8001,
    CONF_TOKEN: "abcde",
}
MOCK_CALLS_ENTRY_WS = {
    "host": "fake",
    "name": "HomeAssistant",
    "port": 8001,
    "timeout": 8,
    "token": "abcde",
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
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote"
    ) as remote_class, patch(
        "homeassistant.components.samsungtv.config_flow.gethostbyname"
    ):
        remote = Mock()
        remote.__enter__ = Mock()
        remote.__exit__ = Mock()
        remote_class.return_value = remote
        yield remote


@pytest.fixture(name="remotews")
def remotews_fixture():
    """Patch the samsungtvws SamsungTVWS."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS"
    ) as remote_class, patch(
        "homeassistant.components.samsungtv.config_flow.gethostbyname"
    ):
        remote = Mock()
        remote.__enter__ = Mock()
        remote.__exit__ = Mock()
        remote.rest_device_info.return_value = {"device": {"type": "Samsung SmartTV"}}
        remote_class.return_value = remote
        remote_class().__enter__().token = "FAKE_TOKEN"
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


async def setup_samsungtv(hass: HomeAssistantType, config: dict):
    """Set up mock Samsung TV."""
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, config)
    await hass.async_block_till_done()


async def test_setup_with_turnon(hass: HomeAssistantType, remote: Mock):
    """Test setup of platform."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert hass.states.get(ENTITY_ID)


async def test_setup_without_turnon(hass: HomeAssistantType, remote: Mock):
    """Test setup of platform."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOTURNON)
    assert hass.states.get(ENTITY_ID_NOTURNON)


async def test_setup_websocket(hass: HomeAssistantType, remotews: Mock, mock_now: Mock):
    """Test setup of platform."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS"
    ) as remote_class, patch(
        "homeassistant.components.samsungtv.config_flow.gethostbyname"
    ):
        enter = Mock()
        type(enter).token = PropertyMock(return_value="987654321")
        remote = Mock()
        remote.__enter__ = Mock(return_value=enter)
        remote.__exit__ = Mock()
        remote.rest_device_info.return_value = {"device": {"type": "Samsung SmartTV"}}
        remote_class.return_value = remote

        await setup_samsungtv(hass, MOCK_CONFIGWS)

        assert remote_class.call_count == 2
        assert remote_class.call_args_list == [
            call(**MOCK_CALLS_WS),
            call(**MOCK_CALLS_DEVICEINFO),
        ]
        assert hass.states.get(ENTITY_ID)


async def test_setup_websocket_2(hass: HomeAssistantType, mock_now: Mock):
    """Test setup of platform from config entry."""
    entity_id = f"{DOMAIN}.fake"

    entry = MockConfigEntry(
        domain=SAMSUNGTV_DOMAIN,
        data=MOCK_ENTRY_WS,
        unique_id=entity_id,
    )
    entry.add_to_hass(hass)

    config_entries = hass.config_entries.async_entries(SAMSUNGTV_DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]

    assert await async_setup_component(hass, SAMSUNGTV_DOMAIN, {})
    await hass.async_block_till_done()

    next_update = mock_now + timedelta(minutes=5)
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS"
    ) as remote, patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert remote.call_count == 1
    assert remote.call_args_list == [call(**MOCK_CALLS_ENTRY_WS)]


async def test_update_on(hass: HomeAssistantType, remote: Mock, mock_now: Mock):
    """Testing update tv on."""
    await setup_samsungtv(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_update_off(hass: HomeAssistantType, remote: Mock, mock_now: Mock):
    """Testing update tv off."""
    await setup_samsungtv(hass, MOCK_CONFIG)

    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[OSError("Boom"), DEFAULT_MOCK],
    ):

        next_update = mock_now + timedelta(minutes=5)
        with patch("homeassistant.util.dt.utcnow", return_value=next_update):
            async_fire_time_changed(hass, next_update)
            await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_OFF


async def test_update_access_denied(
    hass: HomeAssistantType, remote: Mock, mock_now: Mock
):
    """Testing update tv access denied exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)

    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
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


async def test_update_connection_failure(
    hass: HomeAssistantType, remotews: Mock, mock_now: Mock
):
    """Testing update tv connection failure exception."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[OSError("Boom"), DEFAULT_MOCK],
    ):
        await setup_samsungtv(hass, MOCK_CONFIGWS)

        with patch(
            "homeassistant.components.samsungtv.bridge.SamsungTVWS",
            side_effect=ConnectionFailure("Boom"),
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


async def test_update_unhandled_response(
    hass: HomeAssistantType, remote: Mock, mock_now: Mock
):
    """Testing update tv unhandled response exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)

    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[exceptions.UnhandledResponse("Boom"), DEFAULT_MOCK],
    ):

        next_update = mock_now + timedelta(minutes=5)
        with patch("homeassistant.util.dt.utcnow", return_value=next_update):
            async_fire_time_changed(hass, next_update)
            await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_ON


async def test_send_key(hass: HomeAssistantType, remote: Mock):
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


async def test_send_key_broken_pipe(hass: HomeAssistantType, remote: Mock):
    """Testing broken pipe Exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.control = Mock(side_effect=BrokenPipeError("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_send_key_connection_closed_retry_succeed(
    hass: HomeAssistantType, remote: Mock
):
    """Test retry on connection closed."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.control = Mock(
        side_effect=[exceptions.ConnectionClosed("Boom"), DEFAULT_MOCK, DEFAULT_MOCK]
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


async def test_send_key_unhandled_response(hass: HomeAssistantType, remote: Mock):
    """Testing unhandled response exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.control = Mock(side_effect=exceptions.UnhandledResponse("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_send_key_websocketexception(hass: HomeAssistantType, remote: Mock):
    """Testing unhandled response exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.control = Mock(side_effect=WebSocketException("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_send_key_os_error(hass: HomeAssistantType, remote: Mock):
    """Testing broken pipe Exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.control = Mock(side_effect=OSError("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_name(hass: HomeAssistantType, remote: Mock):
    """Test for name property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake"


async def test_state_with_turnon(hass: HomeAssistantType, remote: Mock, delay: Mock):
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


async def test_state_without_turnon(
    hass: HomeAssistantType, remote: Mock, mock_now: Mock
):
    """Test for state property."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOTURNON)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID_NOTURNON)
    assert state.state == STATE_ON
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID_NOTURNON}, True
    )
    state = hass.states.get(ENTITY_ID_NOTURNON)
    assert state.state == STATE_UNAVAILABLE


async def test_supported_features_with_turnon(hass: HomeAssistantType, remote: Mock):
    """Test for supported_features property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_SAMSUNGTV | SUPPORT_TURN_ON
    )


async def test_supported_features_without_turnon(hass: HomeAssistantType, remote: Mock):
    """Test for supported_features property."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOTURNON)
    state = hass.states.get(ENTITY_ID_NOTURNON)
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_SAMSUNGTV


async def test_device_class(hass: HomeAssistantType, remote: Mock):
    """Test for device_class property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_TV


async def test_turn_off_websocket(hass: HomeAssistantType, remotews: Mock):
    """Test for turn_off."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[OSError("Boom"), DEFAULT_MOCK],
    ):
        await setup_samsungtv(hass, MOCK_CONFIGWS)
        assert await hass.services.async_call(
            DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
        )
        # key called
        assert remotews.send_key.call_count == 1
        assert remotews.send_key.call_args_list == [call("KEY_POWER")]


async def test_turn_off_legacy(hass: HomeAssistantType, remote: Mock):
    """Test for turn_off."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_POWEROFF")]


async def test_turn_off_os_error(hass: HomeAssistantType, remote: Mock, caplog):
    """Test for turn_off with OSError."""
    caplog.set_level(logging.DEBUG)
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.close = Mock(side_effect=OSError("BOOM"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert "Could not establish connection" in caplog.text


async def test_volume_up(hass: HomeAssistantType, remote: Mock):
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


async def test_volume_down(hass: HomeAssistantType, remote: Mock):
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


async def test_mute_volume(hass: HomeAssistantType, remote: Mock):
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


async def test_media_play(hass: HomeAssistantType, remote: Mock):
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


async def test_media_pause(hass: HomeAssistantType, remote: Mock):
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


async def test_media_next_track(hass: HomeAssistantType, remote: Mock):
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


async def test_media_previous_track(hass: HomeAssistantType, remote: Mock):
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


async def test_turn_on_with_turnon(hass: HomeAssistantType, remote: Mock, delay: Mock):
    """Test turn on."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert delay.call_count == 1


async def test_turn_on_without_turnon(hass: HomeAssistantType, remote: Mock):
    """Test turn on."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOTURNON)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID_NOTURNON}, True
    )
    # nothing called as not supported feature
    assert remote.control.call_count == 0


async def test_play_media(hass: HomeAssistantType, remote: Mock):
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


async def test_play_media_invalid_type(hass: HomeAssistantType, remote: Mock):
    """Test for play_media with invalid media type."""
    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote:
        url = "https://example.com"
        await setup_samsungtv(hass, MOCK_CONFIG)
        remote.reset_mock()
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


async def test_play_media_channel_as_string(hass: HomeAssistantType, remote: Mock):
    """Test for play_media with invalid channel as string."""
    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote:
        url = "https://example.com"
        await setup_samsungtv(hass, MOCK_CONFIG)
        remote.reset_mock()
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


async def test_play_media_channel_as_non_positive(
    hass: HomeAssistantType, remote: Mock
):
    """Test for play_media with invalid channel as non positive integer."""
    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote:
        await setup_samsungtv(hass, MOCK_CONFIG)
        remote.reset_mock()
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


async def test_select_source(hass: HomeAssistantType, remote: Mock):
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


async def test_select_source_invalid_source(hass: HomeAssistantType, remote: Mock):
    """Test for select_source with invalid source."""
    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote:
        await setup_samsungtv(hass, MOCK_CONFIG)
        remote.reset_mock()
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
