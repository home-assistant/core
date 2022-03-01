"""Tests for samsungtv component."""
import asyncio
from datetime import datetime, timedelta
import logging
from unittest.mock import DEFAULT as DEFAULT_MOCK, AsyncMock, Mock, call, patch

import pytest
from samsungctl import exceptions
from samsungtvws.async_connection import SamsungTVWSAsyncConnection
from samsungtvws.exceptions import ConnectionFailure
from samsungtvws.remote import REMOTE_ENDPOINT, ChannelEmitCommand, SendRemoteKey
from websockets.exceptions import WebSocketException

from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_URL,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SUPPORT_TURN_ON,
)
from homeassistant.components.samsungtv.const import (
    CONF_ON_ACTION,
    DOMAIN as SAMSUNGTV_DOMAIN,
    TIMEOUT_WEBSOCKET,
)
from homeassistant.components.samsungtv.media_player import SUPPORT_SAMSUNGTV
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TOKEN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .conftest import MockAsyncWebsocket

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.fake"
MOCK_CONFIG = {
    SAMSUNGTV_DOMAIN: [
        {
            CONF_HOST: "fake_host",
            CONF_NAME: "fake",
            CONF_PORT: 55000,
            CONF_ON_ACTION: [{"delay": "00:00:01"}],
        }
    ]
}
MOCK_CONFIGWS = {
    SAMSUNGTV_DOMAIN: [
        {
            CONF_HOST: "fake_host",
            CONF_NAME: "fake",
            CONF_PORT: 8001,
            CONF_TOKEN: "123456789",
            CONF_ON_ACTION: [{"delay": "00:00:01"}],
        }
    ]
}
MOCK_CALLS_WS = {
    CONF_HOST: "fake_host",
    CONF_PORT: 8001,
    CONF_TOKEN: "123456789",
    CONF_TIMEOUT: TIMEOUT_WEBSOCKET,
    CONF_NAME: "HomeAssistant",
    "endpoint": REMOTE_ENDPOINT,
}

MOCK_ENTRY_WS = {
    CONF_IP_ADDRESS: "test",
    CONF_HOST: "fake_host",
    CONF_METHOD: "websocket",
    CONF_NAME: "fake",
    CONF_PORT: 8001,
    CONF_TOKEN: "123456789",
}


MOCK_ENTRY_WS_WITH_MAC = {
    CONF_IP_ADDRESS: "test",
    CONF_HOST: "fake_host",
    CONF_METHOD: "websocket",
    CONF_MAC: "aa:bb:cc:dd:ee:ff",
    CONF_NAME: "fake",
    CONF_PORT: 8002,
    CONF_TOKEN: "123456789",
}

ENTITY_ID_NOTURNON = f"{DOMAIN}.fake_noturnon"
MOCK_CONFIG_NOTURNON = {
    SAMSUNGTV_DOMAIN: [
        {CONF_HOST: "fake_noturnon", CONF_NAME: "fake_noturnon", CONF_PORT: 55000}
    ]
}

# Fake mac address in all mediaplayer tests.
pytestmark = pytest.mark.usefixtures("no_mac_address")


@pytest.fixture(name="delay")
def delay_fixture():
    """Patch the delay script function."""
    with patch(
        "homeassistant.components.samsungtv.media_player.Script.async_run"
    ) as delay:
        yield delay


async def setup_samsungtv(hass: HomeAssistant, config: ConfigType) -> None:
    """Set up mock Samsung TV."""
    await async_setup_component(hass, SAMSUNGTV_DOMAIN, config)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("remote")
async def test_setup_with_turnon(hass: HomeAssistant) -> None:
    """Test setup of platform."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert hass.states.get(ENTITY_ID)


@pytest.mark.usefixtures("remote")
async def test_setup_without_turnon(hass: HomeAssistant) -> None:
    """Test setup of platform."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOTURNON)
    assert hass.states.get(ENTITY_ID_NOTURNON)


@pytest.mark.usefixtures("remotews")
async def test_setup_websocket(
    hass: HomeAssistant, ws_connection: MockAsyncWebsocket
) -> None:
    """Test setup of platform."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncConnection"
    ) as remote_class:
        remote = Mock(SamsungTVWSAsyncConnection)
        remote.__aenter__ = AsyncMock(return_value=remote)
        remote.__aexit__ = AsyncMock()
        remote.connection = ws_connection
        remote.start_listening.side_effect = ws_connection.start_listening
        remote.send_command.side_effect = ws_connection.send_command
        remote.token = "123456789"
        remote_class.return_value = remote

        await setup_samsungtv(hass, MOCK_CONFIGWS)

        assert remote_class.call_count == 1
        assert remote_class.call_args_list == [call(**MOCK_CALLS_WS)]
        assert hass.states.get(ENTITY_ID)

        await hass.async_block_till_done()

        config_entries = hass.config_entries.async_entries(SAMSUNGTV_DOMAIN)
        assert len(config_entries) == 1
        assert config_entries[0].data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"


async def test_setup_websocket_2(
    hass: HomeAssistant,
    mock_now: datetime,
    rest_api: Mock,
    ws_connection: MockAsyncWebsocket,
) -> None:
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

    rest_api.rest_device_info.return_value = {
        "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
        "device": {
            "modelName": "82GXARRS",
            "wifiMac": "aa:bb:cc:dd:ee:ff",
            "name": "[TV] Living Room",
            "type": "Samsung SmartTV",
            "networkType": "wireless",
        },
    }
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncConnection"
    ) as remote_class:
        remote = Mock(SamsungTVWSAsyncConnection)
        remote.__aenter__ = AsyncMock(return_value=remote)
        remote.__aexit__ = AsyncMock()
        remote.connection = ws_connection
        remote.start_listening.side_effect = ws_connection.start_listening
        remote.send_command.side_effect = ws_connection.send_command
        remote.token = "987654321"
        remote_class.return_value = remote
        assert await async_setup_component(hass, SAMSUNGTV_DOMAIN, {})
        await hass.async_block_till_done()

        assert config_entries[0].data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"

        next_update = mock_now + timedelta(minutes=5)
        with patch("homeassistant.util.dt.utcnow", return_value=next_update):
            async_fire_time_changed(hass, next_update)
            await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    remote_class.assert_called_once_with(**MOCK_CALLS_WS)


@pytest.mark.usefixtures("remote")
async def test_update_on(hass: HomeAssistant, mock_now: datetime) -> None:
    """Testing update tv on."""
    await setup_samsungtv(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


@pytest.mark.usefixtures("remote")
async def test_update_off(hass: HomeAssistant, mock_now: datetime) -> None:
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


async def test_update_off_ws(
    hass: HomeAssistant, remotews: Mock, mock_now: datetime
) -> None:
    """Testing update tv off."""
    await setup_samsungtv(hass, MOCK_CONFIGWS)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON

    remotews.start_listening = Mock(side_effect=WebSocketException("Boom"))
    remotews.is_alive.return_value = False

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("remote")
async def test_update_access_denied(hass: HomeAssistant, mock_now: datetime) -> None:
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
        next_update = mock_now + timedelta(minutes=10)
        with patch("homeassistant.util.dt.utcnow", return_value=next_update):
            async_fire_time_changed(hass, next_update)
            await hass.async_block_till_done()

    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


async def test_update_connection_failure(
    hass: HomeAssistant, mock_now: datetime, remotews: Mock
) -> None:
    """Testing update tv connection failure exception."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[OSError("Boom"), DEFAULT_MOCK],
    ):
        await setup_samsungtv(hass, MOCK_CONFIGWS)

        with patch.object(
            remotews, "start_listening", side_effect=ConnectionFailure("Boom")
        ), patch.object(remotews, "is_alive", return_value=False):
            next_update = mock_now + timedelta(minutes=5)
            with patch("homeassistant.util.dt.utcnow", return_value=next_update):
                async_fire_time_changed(hass, next_update)
            await hass.async_block_till_done()
            next_update = mock_now + timedelta(minutes=10)
            with patch("homeassistant.util.dt.utcnow", return_value=next_update):
                async_fire_time_changed(hass, next_update)
            await hass.async_block_till_done()

    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("remote")
async def test_update_unhandled_response(
    hass: HomeAssistant, mock_now: datetime
) -> None:
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


@pytest.mark.usefixtures("remote")
async def test_connection_closed_during_update_can_recover(
    hass: HomeAssistant, mock_now: datetime
) -> None:
    """Testing update tv connection closed exception can recover."""
    await setup_samsungtv(hass, MOCK_CONFIG)

    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[exceptions.ConnectionClosed(), DEFAULT_MOCK],
    ):

        next_update = mock_now + timedelta(minutes=5)
        with patch("homeassistant.util.dt.utcnow", return_value=next_update):
            async_fire_time_changed(hass, next_update)
            await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_OFF

        next_update = mock_now + timedelta(minutes=10)
        with patch("homeassistant.util.dt.utcnow", return_value=next_update):
            async_fire_time_changed(hass, next_update)
            await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_ON


async def test_send_key(hass: HomeAssistant, remote: Mock) -> None:
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


async def test_send_key_broken_pipe(hass: HomeAssistant, remote: Mock) -> None:
    """Testing broken pipe Exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.control = Mock(side_effect=BrokenPipeError("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_send_key_connection_closed_retry_succeed(
    hass: HomeAssistant, remote: Mock
) -> None:
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


async def test_send_key_unhandled_response(hass: HomeAssistant, remote: Mock) -> None:
    """Testing unhandled response exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.control = Mock(side_effect=exceptions.UnhandledResponse("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_send_key_websocketexception(hass: HomeAssistant, remotews: Mock) -> None:
    """Testing unhandled response exception."""
    await setup_samsungtv(hass, MOCK_CONFIGWS)
    remotews.send_key = Mock(side_effect=WebSocketException("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_send_key_os_error_ws(hass: HomeAssistant, remotews: Mock) -> None:
    """Testing unhandled response exception."""
    await setup_samsungtv(hass, MOCK_CONFIGWS)
    remotews.send_key = Mock(side_effect=OSError("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_send_key_os_error(hass: HomeAssistant, remote: Mock) -> None:
    """Testing broken pipe Exception."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.control = Mock(side_effect=OSError("Boom"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


@pytest.mark.usefixtures("remote")
async def test_name(hass: HomeAssistant) -> None:
    """Test for name property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake"


@pytest.mark.usefixtures("remote")
async def test_state_with_turnon(hass: HomeAssistant, delay: Mock) -> None:
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


@pytest.mark.usefixtures("remote")
async def test_state_without_turnon(hass: HomeAssistant) -> None:
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
    # Should be STATE_UNAVAILABLE after the timer expires
    assert state.state == STATE_OFF

    next_update = dt_util.utcnow() + timedelta(seconds=20)
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError,
    ), patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID_NOTURNON)
    # Should be STATE_UNAVAILABLE since there is no way to turn it back on
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("remote")
async def test_supported_features_with_turnon(hass: HomeAssistant) -> None:
    """Test for supported_features property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_SAMSUNGTV | SUPPORT_TURN_ON
    )


@pytest.mark.usefixtures("remote")
async def test_supported_features_without_turnon(hass: HomeAssistant) -> None:
    """Test for supported_features property."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOTURNON)
    state = hass.states.get(ENTITY_ID_NOTURNON)
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_SAMSUNGTV


@pytest.mark.usefixtures("remote")
async def test_device_class(hass: HomeAssistant) -> None:
    """Test for device_class property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_DEVICE_CLASS] is MediaPlayerDeviceClass.TV.value


async def test_turn_off_websocket(hass: HomeAssistant, remotews: Mock) -> None:
    """Test for turn_off."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[OSError("Boom"), DEFAULT_MOCK],
    ):
        await setup_samsungtv(hass, MOCK_CONFIGWS)
        remotews.send_command.reset_mock()

        assert await hass.services.async_call(
            DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
        )
        # key called
        assert remotews.send_command.call_count == 1
        command = remotews.send_command.call_args_list[0].args[0]
        assert isinstance(command, SendRemoteKey)
        assert command.params["DataOfCmd"] == "KEY_POWER"

        assert await hass.services.async_call(
            DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
        )
        # key not called
        assert remotews.send_command.call_count == 1


async def test_turn_off_legacy(hass: HomeAssistant, remote: Mock) -> None:
    """Test for turn_off."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOTURNON)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID_NOTURNON}, True
    )
    # key called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY_POWEROFF")]


async def test_turn_off_os_error(
    hass: HomeAssistant, remote: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for turn_off with OSError."""
    caplog.set_level(logging.DEBUG)
    await setup_samsungtv(hass, MOCK_CONFIG)
    remote.close = Mock(side_effect=OSError("BOOM"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert "Could not establish connection" in caplog.text


async def test_turn_off_ws_os_error(
    hass: HomeAssistant, remotews: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for turn_off with OSError."""
    caplog.set_level(logging.DEBUG)
    await setup_samsungtv(hass, MOCK_CONFIGWS)
    remotews.close = Mock(side_effect=OSError("BOOM"))
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert "Could not establish connection" in caplog.text


async def test_volume_up(hass: HomeAssistant, remote: Mock) -> None:
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


async def test_volume_down(hass: HomeAssistant, remote: Mock) -> None:
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


async def test_mute_volume(hass: HomeAssistant, remote: Mock) -> None:
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


async def test_media_play(hass: HomeAssistant, remote: Mock) -> None:
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

    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_PLAY"), call("KEY_PAUSE")]
    assert remote.close.call_count == 2
    assert remote.close.call_args_list == [call(), call()]


async def test_media_pause(hass: HomeAssistant, remote: Mock) -> None:
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

    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_PAUSE"), call("KEY_PLAY")]
    assert remote.close.call_count == 2
    assert remote.close.call_args_list == [call(), call()]


async def test_media_next_track(hass: HomeAssistant, remote: Mock) -> None:
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


async def test_media_previous_track(hass: HomeAssistant, remote: Mock) -> None:
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


@pytest.mark.usefixtures("remote")
async def test_turn_on_with_turnon(hass: HomeAssistant, delay: Mock) -> None:
    """Test turn on."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert delay.call_count == 1


@pytest.mark.usefixtures("remotews")
async def test_turn_on_wol(hass: HomeAssistant) -> None:
    """Test turn on."""
    entry = MockConfigEntry(
        domain=SAMSUNGTV_DOMAIN,
        data=MOCK_ENTRY_WS_WITH_MAC,
        unique_id="any",
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, SAMSUNGTV_DOMAIN, {})
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.samsungtv.media_player.send_magic_packet"
    ) as mock_send_magic_packet:
        assert await hass.services.async_call(
            DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
        )
        await hass.async_block_till_done()
    assert mock_send_magic_packet.called


async def test_turn_on_without_turnon(hass: HomeAssistant, remote: Mock) -> None:
    """Test turn on."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOTURNON)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID_NOTURNON}, True
    )
    # nothing called as not supported feature
    assert remote.control.call_count == 0


async def test_play_media(hass: HomeAssistant, remote: Mock) -> None:
    """Test for play_media."""
    asyncio_sleep = asyncio.sleep
    sleeps = []

    async def sleep(duration):
        sleeps.append(duration)
        await asyncio_sleep(0)

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


async def test_play_media_invalid_type(hass: HomeAssistant) -> None:
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


async def test_play_media_channel_as_string(hass: HomeAssistant) -> None:
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


async def test_play_media_channel_as_non_positive(hass: HomeAssistant) -> None:
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


async def test_select_source(hass: HomeAssistant, remote: Mock) -> None:
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


async def test_select_source_invalid_source(hass: HomeAssistant) -> None:
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


async def test_play_media_app(hass: HomeAssistant, remotews: Mock) -> None:
    """Test for play_media."""
    await setup_samsungtv(hass, MOCK_CONFIGWS)
    remotews.send_command.reset_mock()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_APP,
            ATTR_MEDIA_CONTENT_ID: "3201608010191",
        },
        True,
    )
    assert remotews.send_command.call_count == 1
    command = remotews.send_command.call_args_list[0].args[0]
    assert isinstance(command, ChannelEmitCommand)
    assert command.params["data"]["appId"] == "3201608010191"


async def test_select_source_app(hass: HomeAssistant, remotews: Mock) -> None:
    """Test for select_source."""
    await setup_samsungtv(hass, MOCK_CONFIGWS)
    remotews.send_command.reset_mock()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "Deezer"},
        True,
    )
    assert remotews.send_command.call_count == 1
    command = remotews.send_command.call_args_list[0].args[0]
    assert isinstance(command, ChannelEmitCommand)
    assert command.params["data"]["appId"] == "3201608010191"
