"""Tests for samsungtv component."""

from copy import deepcopy
from datetime import timedelta
import logging
from unittest.mock import DEFAULT as DEFAULT_MOCK, AsyncMock, Mock, call, patch

from async_upnp_client.exceptions import (
    UpnpActionResponseError,
    UpnpCommunicationError,
    UpnpConnectionError,
    UpnpError,
    UpnpResponseError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from samsungctl import exceptions
from samsungtvws.async_remote import SamsungTVWSAsyncRemote
from samsungtvws.command import SamsungTVSleepCommand
from samsungtvws.encrypted.remote import (
    SamsungTVEncryptedCommand,
    SamsungTVEncryptedWSAsyncRemote,
)
from samsungtvws.exceptions import ConnectionFailure, HttpApiError, UnauthorizedError
from samsungtvws.remote import ChannelEmitCommand, SendRemoteKey
from websockets.exceptions import ConnectionClosedError, WebSocketException

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    MediaPlayerDeviceClass,
    MediaType,
)
from homeassistant.components.samsungtv.const import (
    CONF_SSDP_RENDERING_CONTROL_LOCATION,
    DOMAIN,
    ENCRYPTED_WEBSOCKET_PORT,
    ENTRY_RELOAD_COOLDOWN,
    METHOD_ENCRYPTED_WEBSOCKET,
    METHOD_WEBSOCKET,
    TIMEOUT_WEBSOCKET,
)
from homeassistant.components.samsungtv.media_player import SUPPORT_SAMSUNGTV
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    CONF_HOST,
    CONF_MAC,
    CONF_METHOD,
    CONF_MODEL,
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
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceNotSupported
from homeassistant.setup import async_setup_component

from . import setup_samsungtv_entry
from .const import (
    MOCK_ENTRY_WS_WITH_MAC,
    MOCK_ENTRYDATA_ENCRYPTED_WS,
    MOCK_ENTRYDATA_LEGACY,
    SAMPLE_DEVICE_INFO_WIFI,
)

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
)

ENTITY_ID = f"{MP_DOMAIN}.mock_title"
MOCK_CONFIGWS = {
    CONF_HOST: "fake_host",
    CONF_NAME: "fake",
    CONF_PORT: 8001,
    CONF_TOKEN: "123456789",
    CONF_METHOD: METHOD_WEBSOCKET,
}
MOCK_CALLS_WS = {
    CONF_HOST: "fake_host",
    CONF_PORT: 8001,
    CONF_TOKEN: "123456789",
    CONF_TIMEOUT: TIMEOUT_WEBSOCKET,
    CONF_NAME: "HomeAssistant",
}

MOCK_ENTRY_WS = {
    CONF_HOST: "fake_host",
    CONF_METHOD: "websocket",
    CONF_NAME: "fake",
    CONF_PORT: 8001,
    CONF_TOKEN: "123456789",
    CONF_SSDP_RENDERING_CONTROL_LOCATION: "https://any",
}


@pytest.mark.usefixtures("remote_legacy")
async def test_setup(hass: HomeAssistant) -> None:
    """Test setup of platform."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    assert hass.states.get(ENTITY_ID)


@pytest.mark.usefixtures("remotews", "rest_api")
async def test_setup_websocket(hass: HomeAssistant) -> None:
    """Test setup of platform."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote"
    ) as remote_class:
        remote = Mock(SamsungTVWSAsyncRemote)
        remote.__aenter__ = AsyncMock(return_value=remote)
        remote.__aexit__ = AsyncMock()
        remote.token = "123456789"
        remote_class.return_value = remote

        await setup_samsungtv_entry(hass, MOCK_CONFIGWS)

        assert remote_class.call_count == 1
        assert remote_class.call_args_list == [call(**MOCK_CALLS_WS)]
        assert hass.states.get(ENTITY_ID)

        await hass.async_block_till_done()

        config_entries = hass.config_entries.async_entries(DOMAIN)
        assert len(config_entries) == 1
        assert config_entries[0].data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"


@pytest.mark.usefixtures("rest_api")
async def test_setup_websocket_2(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test setup of platform from config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY_WS,
    )
    entry.add_to_hass(hass)

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote"
    ) as remote_class:
        remote = Mock(SamsungTVWSAsyncRemote)
        remote.__aenter__ = AsyncMock(return_value=remote)
        remote.__aexit__ = AsyncMock()
        remote.token = "987654321"
        remote_class.return_value = remote
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert config_entries[0].data[CONF_MAC] == "aa:bb:aa:aa:aa:aa"

        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state
    remote_class.assert_called_once_with(**MOCK_CALLS_WS)


@pytest.mark.usefixtures("rest_api")
async def test_setup_encrypted_websocket(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test setup of platform from config entry."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVEncryptedWSAsyncRemote"
    ) as remote_class:
        remote = Mock(SamsungTVEncryptedWSAsyncRemote)
        remote.__aenter__ = AsyncMock(return_value=remote)
        remote.__aexit__ = AsyncMock()
        remote_class.return_value = remote

        await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state
    remote_class.assert_called_once()


@pytest.mark.usefixtures("remote_legacy")
async def test_update_on(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Testing update tv on."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


@pytest.mark.usefixtures("remote_legacy")
async def test_update_off(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Testing update tv off."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)

    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[OSError("Boom"), DEFAULT_MOCK],
    ):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_UNAVAILABLE


async def test_update_off_ws_no_power_state(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, remotews: Mock, rest_api: Mock
) -> None:
    """Testing update tv off."""
    await setup_samsungtv_entry(hass, MOCK_CONFIGWS)
    # device_info should only get called once, as part of the setup
    rest_api.rest_device_info.assert_called_once()
    rest_api.rest_device_info.reset_mock()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON

    remotews.start_listening = Mock(side_effect=WebSocketException("Boom"))
    remotews.is_alive.return_value = False

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    rest_api.rest_device_info.assert_not_called()


@pytest.mark.usefixtures("remotews")
async def test_update_off_ws_with_power_state(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, remotews: Mock, rest_api: Mock
) -> None:
    """Testing update tv off."""
    with (
        patch.object(
            rest_api, "rest_device_info", side_effect=HttpApiError
        ) as mock_device_info,
        patch.object(
            remotews, "start_listening", side_effect=WebSocketException("Boom")
        ) as mock_start_listening,
    ):
        await setup_samsungtv_entry(hass, MOCK_CONFIGWS)

        mock_device_info.assert_called_once()
        mock_start_listening.assert_called_once()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE

    # First update uses start_listening once, and initialises device_info
    device_info = deepcopy(SAMPLE_DEVICE_INFO_WIFI)
    device_info["device"]["PowerState"] = "on"
    rest_api.rest_device_info.return_value = device_info

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    remotews.start_listening.assert_called_once()
    rest_api.rest_device_info.assert_called_once()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON

    # After initial update, start_listening shouldn't be called
    remotews.start_listening.reset_mock()

    # Second update uses device_info(ON)
    rest_api.rest_device_info.reset_mock()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    rest_api.rest_device_info.assert_called_once()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON

    # Third update uses device_info (OFF)
    rest_api.rest_device_info.reset_mock()
    device_info["device"]["PowerState"] = "off"

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    rest_api.rest_device_info.assert_called_once()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE

    remotews.start_listening.assert_not_called()


async def test_update_off_encryptedws(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    remoteencws: Mock,
    rest_api: Mock,
) -> None:
    """Testing update tv off."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    rest_api.rest_device_info.assert_called_once()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON

    remoteencws.start_listening = Mock(side_effect=WebSocketException("Boom"))
    remoteencws.is_alive.return_value = False

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    rest_api.rest_device_info.assert_called_once()


@pytest.mark.usefixtures("remote_legacy")
async def test_update_access_denied(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Testing update tv access denied exception."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)

    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=exceptions.AccessDenied("Boom"),
    ):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("rest_api")
async def test_update_ws_connection_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    remotews: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Testing update tv connection failure exception."""
    await setup_samsungtv_entry(hass, MOCK_CONFIGWS)

    with (
        patch.object(
            remotews,
            "start_listening",
            side_effect=ConnectionFailure('{"event": "ms.voiceApp.hide"}'),
        ),
        patch.object(remotews, "is_alive", return_value=False),
    ):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        "Unexpected ConnectionFailure trying to get remote for fake_host, please "
        'report this issue: ConnectionFailure(\'{"event": "ms.voiceApp.hide"}\')'
        in caplog.text
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("rest_api")
async def test_update_ws_connection_closed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, remotews: Mock
) -> None:
    """Testing update tv connection failure exception."""
    await setup_samsungtv_entry(hass, MOCK_CONFIGWS)

    with (
        patch.object(
            remotews, "start_listening", side_effect=ConnectionClosedError(None, None)
        ),
        patch.object(remotews, "is_alive", return_value=False),
    ):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("rest_api")
async def test_update_ws_unauthorized_error(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, remotews: Mock
) -> None:
    """Testing update tv unauthorized failure exception."""
    await setup_samsungtv_entry(hass, MOCK_CONFIGWS)

    with (
        patch.object(remotews, "start_listening", side_effect=UnauthorizedError),
        patch.object(remotews, "is_alive", return_value=False),
    ):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("remote_legacy")
async def test_update_unhandled_response(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Testing update tv unhandled response exception."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)

    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[exceptions.UnhandledResponse("Boom"), DEFAULT_MOCK],
    ):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_ON


@pytest.mark.usefixtures("remote_legacy")
async def test_connection_closed_during_update_can_recover(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Testing update tv connection closed exception can recover."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)

    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[exceptions.ConnectionClosed(), DEFAULT_MOCK],
    ):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_UNAVAILABLE

        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_ON


async def test_send_key(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Test for send key."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    # key called
    assert remote_legacy.control.call_count == 1
    assert remote_legacy.control.call_args_list == [call("KEY_VOLUP")]
    assert state.state == STATE_ON


async def test_send_key_broken_pipe(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Testing broken pipe Exception."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    remote_legacy.control = Mock(side_effect=BrokenPipeError("Boom"))
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_send_key_connection_closed_retry_succeed(
    hass: HomeAssistant, remote_legacy: Mock
) -> None:
    """Test retry on connection closed."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    remote_legacy.control = Mock(
        side_effect=[exceptions.ConnectionClosed("Boom"), DEFAULT_MOCK, DEFAULT_MOCK]
    )
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    # key because of retry two times
    assert remote_legacy.control.call_count == 2
    assert remote_legacy.control.call_args_list == [
        call("KEY_VOLUP"),
        call("KEY_VOLUP"),
    ]
    assert state.state == STATE_ON


async def test_send_key_unhandled_response(
    hass: HomeAssistant, remote_legacy: Mock
) -> None:
    """Testing unhandled response exception."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    remote_legacy.control = Mock(side_effect=exceptions.UnhandledResponse("Boom"))
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
        )
    assert err.value.translation_key == "error_sending_command"
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


@pytest.mark.usefixtures("rest_api")
async def test_send_key_websocketexception(hass: HomeAssistant, remotews: Mock) -> None:
    """Testing unhandled response exception."""
    await setup_samsungtv_entry(hass, MOCK_CONFIGWS)
    remotews.send_commands = Mock(side_effect=WebSocketException("Boom"))
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


@pytest.mark.usefixtures("rest_api")
async def test_send_key_websocketexception_encrypted(
    hass: HomeAssistant, remoteencws: Mock
) -> None:
    """Testing unhandled response exception."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)
    remoteencws.send_commands = Mock(side_effect=WebSocketException("Boom"))
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


@pytest.mark.usefixtures("rest_api")
async def test_send_key_os_error_ws(hass: HomeAssistant, remotews: Mock) -> None:
    """Testing unhandled response exception."""
    await setup_samsungtv_entry(hass, MOCK_CONFIGWS)
    remotews.send_commands = Mock(side_effect=OSError("Boom"))
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


@pytest.mark.usefixtures("rest_api")
async def test_send_key_os_error_ws_encrypted(
    hass: HomeAssistant, remoteencws: Mock
) -> None:
    """Testing unhandled response exception."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)
    remoteencws.send_commands = Mock(side_effect=OSError("Boom"))
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_send_key_os_error(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Testing broken pipe Exception."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    remote_legacy.control = Mock(side_effect=OSError("Boom"))
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


@pytest.mark.usefixtures("remote_legacy")
async def test_name(hass: HomeAssistant) -> None:
    """Test for name property."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Mock Title"


@pytest.mark.usefixtures("remote_legacy")
async def test_state(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test for state property."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    # Should be STATE_UNAVAILABLE after the timer expires
    assert state.state == STATE_OFF

    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=OSError,
    ):
        freezer.tick(timedelta(seconds=20))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    # Should be STATE_UNAVAILABLE since there is no way to turn it back on
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("remote_legacy")
async def test_supported_features(hass: HomeAssistant) -> None:
    """Test for supported_features property."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_SAMSUNGTV


@pytest.mark.usefixtures("remote_legacy")
async def test_device_class(hass: HomeAssistant) -> None:
    """Test for device_class property."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_DEVICE_CLASS] == MediaPlayerDeviceClass.TV


@pytest.mark.usefixtures("rest_api")
async def test_turn_off_websocket(
    hass: HomeAssistant, remotews: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for turn_off."""
    remotews.app_list_data = load_json_object_fixture(
        "ws_installed_app_event.json", DOMAIN
    )
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[OSError("Boom"), DEFAULT_MOCK],
    ):
        await setup_samsungtv_entry(hass, MOCK_CONFIGWS)

    remotews.send_commands.reset_mock()

    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remotews.send_commands.call_count == 1
    commands = remotews.send_commands.call_args_list[0].args[0]
    assert len(commands) == 1
    assert isinstance(commands[0], SendRemoteKey)
    assert commands[0].params["DataOfCmd"] == "KEY_POWER"

    # commands not sent : power off in progress
    remotews.send_commands.reset_mock()
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert "TV is powering off, not sending keys: ['KEY_VOLUP']" in caplog.text
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "Deezer"},
        True,
    )
    assert "TV is powering off, not sending launch_app command" in caplog.text
    remotews.send_commands.assert_not_called()


async def test_turn_off_websocket_frame(
    hass: HomeAssistant, remotews: Mock, rest_api: Mock
) -> None:
    """Test for turn_off."""
    rest_api.rest_device_info.return_value = load_json_object_fixture(
        "device_info_UE43LS003.json", DOMAIN
    )
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote",
        side_effect=[OSError("Boom"), DEFAULT_MOCK],
    ):
        await setup_samsungtv_entry(hass, MOCK_CONFIGWS)

    remotews.send_commands.reset_mock()

    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remotews.send_commands.call_count == 1
    commands = remotews.send_commands.call_args_list[0].args[0]
    assert len(commands) == 3
    assert isinstance(commands[0], SendRemoteKey)
    assert commands[0].params["Cmd"] == "Press"
    assert commands[0].params["DataOfCmd"] == "KEY_POWER"
    assert isinstance(commands[1], SamsungTVSleepCommand)
    assert commands[1].delay == 3
    assert isinstance(commands[2], SendRemoteKey)
    assert commands[2].params["Cmd"] == "Release"
    assert commands[2].params["DataOfCmd"] == "KEY_POWER"


async def test_turn_off_encrypted_websocket(
    hass: HomeAssistant, remoteencws: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for turn_off."""
    entry_data = deepcopy(MOCK_ENTRYDATA_ENCRYPTED_WS)
    entry_data[CONF_MODEL] = "UE48UNKNOWN"
    await setup_samsungtv_entry(hass, entry_data)

    remoteencws.send_commands.reset_mock()

    caplog.clear()
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remoteencws.send_commands.call_count == 1
    commands = remoteencws.send_commands.call_args_list[0].args[0]
    assert len(commands) == 2
    assert isinstance(command := commands[0], SamsungTVEncryptedCommand)
    assert command.body["param3"] == "KEY_POWEROFF"
    assert isinstance(command := commands[1], SamsungTVEncryptedCommand)
    assert command.body["param3"] == "KEY_POWER"
    assert "Unknown power_off command for UE48UNKNOWN (fake_host)" in caplog.text

    # commands not sent : power off in progress
    remoteencws.send_commands.reset_mock()
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert "TV is powering off, not sending keys: ['KEY_VOLUP']" in caplog.text
    remoteencws.send_commands.assert_not_called()


@pytest.mark.parametrize(
    ("model", "expected_key_type"),
    [("UE50H6400", "KEY_POWEROFF"), ("UN75JU641D", "KEY_POWER")],
)
async def test_turn_off_encrypted_websocket_key_type(
    hass: HomeAssistant,
    remoteencws: Mock,
    caplog: pytest.LogCaptureFixture,
    model: str,
    expected_key_type: str,
) -> None:
    """Test for turn_off."""
    entry_data = deepcopy(MOCK_ENTRYDATA_ENCRYPTED_WS)
    entry_data[CONF_MODEL] = model
    await setup_samsungtv_entry(hass, entry_data)

    remoteencws.send_commands.reset_mock()

    caplog.clear()
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remoteencws.send_commands.call_count == 1
    commands = remoteencws.send_commands.call_args_list[0].args[0]
    assert len(commands) == 1
    assert isinstance(command := commands[0], SamsungTVEncryptedCommand)
    assert command.body["param3"] == expected_key_type
    assert "Unknown power_off command for" not in caplog.text


async def test_turn_off_legacy(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Test for turn_off."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remote_legacy.control.call_count == 1
    assert remote_legacy.control.call_args_list == [call("KEY_POWEROFF")]


async def test_turn_off_os_error(
    hass: HomeAssistant, remote_legacy: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for turn_off with OSError."""
    caplog.set_level(logging.DEBUG)
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    remote_legacy.close = Mock(side_effect=OSError("BOOM"))
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert "Could not establish connection" in caplog.text


@pytest.mark.usefixtures("rest_api")
async def test_turn_off_ws_os_error(
    hass: HomeAssistant, remotews: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for turn_off with OSError."""
    caplog.set_level(logging.DEBUG)
    await setup_samsungtv_entry(hass, MOCK_CONFIGWS)
    remotews.close = Mock(side_effect=OSError("BOOM"))
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert "Error closing connection" in caplog.text


@pytest.mark.usefixtures("rest_api")
async def test_turn_off_encryptedws_os_error(
    hass: HomeAssistant, remoteencws: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for turn_off with OSError."""
    caplog.set_level(logging.DEBUG)
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)
    remoteencws.close = Mock(side_effect=OSError("BOOM"))
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert "Error closing connection" in caplog.text


async def test_volume_up(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Test for volume_up."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remote_legacy.control.call_count == 1
    assert remote_legacy.control.call_args_list == [call("KEY_VOLUP")]


async def test_volume_down(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Test for volume_down."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_DOWN, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remote_legacy.control.call_count == 1
    assert remote_legacy.control.call_args_list == [call("KEY_VOLDOWN")]


async def test_mute_volume(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Test for mute_volume."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        True,
    )
    # key called
    assert remote_legacy.control.call_count == 1
    assert remote_legacy.control.call_args_list == [call("KEY_MUTE")]


async def test_media_play(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Test for media_play."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_MEDIA_PLAY, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remote_legacy.control.call_count == 1
    assert remote_legacy.control.call_args_list == [call("KEY_PLAY")]

    await hass.services.async_call(
        MP_DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remote_legacy.control.call_count == 2
    assert remote_legacy.control.call_args_list == [call("KEY_PLAY"), call("KEY_PAUSE")]


async def test_media_pause(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Test for media_pause."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_MEDIA_PAUSE, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remote_legacy.control.call_count == 1
    assert remote_legacy.control.call_args_list == [call("KEY_PAUSE")]

    await hass.services.async_call(
        MP_DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remote_legacy.control.call_count == 2
    assert remote_legacy.control.call_args_list == [call("KEY_PAUSE"), call("KEY_PLAY")]


async def test_media_next_track(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Test for media_next_track."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_MEDIA_NEXT_TRACK, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key  called
    assert remote_legacy.control.call_count == 1
    assert remote_legacy.control.call_args_list == [call("KEY_CHUP")]


async def test_media_previous_track(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Test for media_previous_track."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key called
    assert remote_legacy.control.call_count == 1
    assert remote_legacy.control.call_args_list == [call("KEY_CHDOWN")]


@pytest.mark.usefixtures("remotews", "rest_api")
async def test_turn_on_wol(hass: HomeAssistant) -> None:
    """Test turn on."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY_WS_WITH_MAC,
        unique_id="be9554b9-c9fb-41f4-8920-22da015376a4",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.samsungtv.entity.send_magic_packet"
    ) as mock_send_magic_packet:
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
        )
        await hass.async_block_till_done()
    assert mock_send_magic_packet.called


async def test_turn_on_without_turnon(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Test turn on."""
    await async_setup_component(hass, "homeassistant", {})
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    with pytest.raises(ServiceNotSupported, match="does not support action"):
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
        )
    # nothing called as not supported feature
    assert remote_legacy.control.call_count == 0


async def test_play_media(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Test for play_media."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    with patch("homeassistant.components.samsungtv.bridge.asyncio.sleep") as sleep:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
                ATTR_MEDIA_CONTENT_ID: "576",
            },
            True,
        )
    # keys and update called
    assert remote_legacy.control.call_count == 4
    assert remote_legacy.control.call_args_list == [
        call("KEY_5"),
        call("KEY_7"),
        call("KEY_6"),
        call("KEY_ENTER"),
    ]
    assert sleep.call_count == 3


async def test_play_media_invalid_type(hass: HomeAssistant) -> None:
    """Test for play_media with invalid media type."""
    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote:
        url = "https://example.com"
        await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
        remote.reset_mock()
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.URL,
                ATTR_MEDIA_CONTENT_ID: url,
            },
            True,
        )
        # control not called
        assert remote.control.call_count == 0


async def test_play_media_channel_as_string(hass: HomeAssistant) -> None:
    """Test for play_media with invalid channel as string."""
    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote:
        url = "https://example.com"
        await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
        remote.reset_mock()
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
                ATTR_MEDIA_CONTENT_ID: url,
            },
            True,
        )
        # control not called
        assert remote.control.call_count == 0


async def test_play_media_channel_as_non_positive(hass: HomeAssistant) -> None:
    """Test for play_media with invalid channel as non positive integer."""
    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote:
        await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
        remote.reset_mock()
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
                ATTR_MEDIA_CONTENT_ID: "-4",
            },
            True,
        )
        # control not called
        assert remote.control.call_count == 0


async def test_select_source(hass: HomeAssistant, remote_legacy: Mock) -> None:
    """Test for select_source."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "HDMI"},
        True,
    )
    # key called
    assert remote_legacy.control.call_count == 1
    assert remote_legacy.control.call_args_list == [call("KEY_HDMI")]


async def test_select_source_invalid_source(hass: HomeAssistant) -> None:
    """Test for select_source with invalid source."""

    source = "INVALID"

    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote:
        await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_LEGACY)
        remote.reset_mock()
        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                MP_DOMAIN,
                SERVICE_SELECT_SOURCE,
                {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: source},
                True,
            )
        # control not called
        assert remote.control.call_count == 0
        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "source_unsupported"
        assert exc_info.value.translation_placeholders == {
            "entity": ENTITY_ID,
            "source": source,
        }


@pytest.mark.usefixtures("rest_api")
async def test_play_media_app(hass: HomeAssistant, remotews: Mock) -> None:
    """Test for play_media."""
    await setup_samsungtv_entry(hass, MOCK_CONFIGWS)
    remotews.send_commands.reset_mock()

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.APP,
            ATTR_MEDIA_CONTENT_ID: "3201608010191",
        },
        True,
    )
    assert remotews.send_commands.call_count == 1
    commands = remotews.send_commands.call_args_list[0].args[0]
    assert len(commands) == 1
    assert isinstance(commands[0], ChannelEmitCommand)
    assert commands[0].params["data"]["appId"] == "3201608010191"


@pytest.mark.usefixtures("rest_api")
async def test_select_source_app(hass: HomeAssistant, remotews: Mock) -> None:
    """Test for select_source."""
    remotews.app_list_data = load_json_object_fixture(
        "ws_installed_app_event.json", DOMAIN
    )
    await setup_samsungtv_entry(hass, MOCK_CONFIGWS)
    remotews.send_commands.reset_mock()

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "Deezer"},
        True,
    )
    assert remotews.send_commands.call_count == 1
    commands = remotews.send_commands.call_args_list[0].args[0]
    assert len(commands) == 1
    assert isinstance(commands[0], ChannelEmitCommand)
    assert commands[0].params["data"]["appId"] == "3201608010191"


@pytest.mark.usefixtures("rest_api")
async def test_websocket_unsupported_remote_control(
    hass: HomeAssistant,
    remotews: Mock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for turn_off."""
    entry = await setup_samsungtv_entry(hass, MOCK_ENTRY_WS)

    assert entry.data[CONF_METHOD] == METHOD_WEBSOCKET
    assert entry.data[CONF_PORT] == 8001

    remotews.send_commands.reset_mock()

    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    remotews.raise_mock_ws_event_callback(
        "ms.error",
        {
            "event": "ms.error",
            "data": {"message": "unrecognized method value : ms.remote.control"},
        },
    )

    # key called
    assert remotews.send_commands.call_count == 1
    commands = remotews.send_commands.call_args_list[0].args[0]
    assert len(commands) == 1
    assert isinstance(commands[0], SendRemoteKey)
    assert commands[0].params["DataOfCmd"] == "KEY_POWER"

    # error logged
    assert (
        "Your TV seems to be unsupported by SamsungTVWSBridge and needs a PIN: "
        "'unrecognized method value : ms.remote.control'" in caplog.text
    )

    # Wait config_entry reload
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=ENTRY_RELOAD_COOLDOWN))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # ensure reauth triggered, and method/port updated
    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
    assert entry.data[CONF_METHOD] == METHOD_ENCRYPTED_WEBSOCKET
    assert entry.data[CONF_PORT] == ENCRYPTED_WEBSOCKET_PORT
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("remotews", "rest_api", "upnp_notify_server")
async def test_volume_control_upnp(hass: HomeAssistant, dmr_device: Mock) -> None:
    """Test for Upnp volume control."""
    await setup_samsungtv_entry(hass, MOCK_ENTRY_WS)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.44
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False

    # Upnp action succeeds
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        True,
    )
    dmr_device.async_set_volume_level.assert_called_once_with(0.5)

    # Upnp action failed
    dmr_device.async_set_volume_level.reset_mock()
    dmr_device.async_set_volume_level.side_effect = UpnpActionResponseError(
        status=500, error_code=501, error_desc="Action Failed"
    )
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_SET,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.6},
            True,
        )
    assert err.value.translation_key == "error_set_volume"
    dmr_device.async_set_volume_level.assert_called_once_with(0.6)


@pytest.mark.usefixtures("remotews", "rest_api")
async def test_upnp_not_available(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for volume control when Upnp is not available."""
    await setup_samsungtv_entry(hass, MOCK_ENTRY_WS)
    assert "Unable to create Upnp DMR device" in caplog.text

    # Upnp action fails
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.6},
        True,
    )
    assert "Upnp services are not available" in caplog.text


@pytest.mark.usefixtures("remotews", "rest_api", "upnp_factory")
async def test_upnp_missing_service(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for volume control when Upnp is not available."""
    await setup_samsungtv_entry(hass, MOCK_ENTRY_WS)
    assert "Unable to create Upnp DMR device" in caplog.text

    # Upnp action fails
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.6},
        True,
    )
    assert "Upnp services are not available" in caplog.text


@pytest.mark.usefixtures("remotews", "rest_api")
async def test_upnp_shutdown(
    hass: HomeAssistant,
    dmr_device: Mock,
    upnp_notify_server: Mock,
) -> None:
    """Ensure that Upnp cleanup takes effect."""
    entry = await setup_samsungtv_entry(hass, MOCK_ENTRY_WS)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON

    assert await hass.config_entries.async_unload(entry.entry_id)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE

    dmr_device.async_unsubscribe_services.assert_called_once()
    upnp_notify_server.async_stop_server.assert_called_once()


@pytest.mark.usefixtures("remotews", "rest_api", "upnp_notify_server")
async def test_upnp_subscribe_events(hass: HomeAssistant, dmr_device: Mock) -> None:
    """Test for Upnp event feedback."""
    await setup_samsungtv_entry(hass, MOCK_ENTRY_WS)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.44
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False

    # DMR Devices gets updated, and raise event
    dmr_device.volume_level = 0
    dmr_device.is_volume_muted = True
    dmr_device.raise_event(None, None)

    # State gets updated without the need to wait for next update
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is True


@pytest.mark.usefixtures("remotews", "rest_api")
async def test_upnp_subscribe_events_upnperror(
    hass: HomeAssistant,
    dmr_device: Mock,
    upnp_notify_server: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for failure to subscribe Upnp services."""
    with patch.object(dmr_device, "async_subscribe_services", side_effect=UpnpError):
        await setup_samsungtv_entry(hass, MOCK_ENTRY_WS)

    upnp_notify_server.async_stop_server.assert_called_once()
    assert "Error while subscribing during device connect" in caplog.text


@pytest.mark.usefixtures("remotews", "rest_api")
async def test_upnp_subscribe_events_upnpresponseerror(
    hass: HomeAssistant,
    dmr_device: Mock,
    upnp_notify_server: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for failure to subscribe Upnp services."""
    with patch.object(
        dmr_device,
        "async_subscribe_services",
        side_effect=UpnpResponseError(status=501),
    ):
        await setup_samsungtv_entry(hass, MOCK_ENTRY_WS)

    upnp_notify_server.async_stop_server.assert_not_called()
    assert "Device rejected subscription" in caplog.text


@pytest.mark.usefixtures("rest_api", "upnp_notify_server")
async def test_upnp_re_subscribe_events(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    remotews: Mock,
    dmr_device: Mock,
) -> None:
    """Test for Upnp event feedback."""
    await setup_samsungtv_entry(hass, MOCK_ENTRY_WS)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert dmr_device.async_subscribe_services.call_count == 1
    assert dmr_device.async_unsubscribe_services.call_count == 0

    with (
        patch.object(
            remotews, "start_listening", side_effect=WebSocketException("Boom")
        ),
        patch.object(remotews, "is_alive", return_value=False),
    ):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert dmr_device.async_subscribe_services.call_count == 1
    assert dmr_device.async_unsubscribe_services.call_count == 1

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert dmr_device.async_subscribe_services.call_count == 2
    assert dmr_device.async_unsubscribe_services.call_count == 1


@pytest.mark.usefixtures("rest_api", "upnp_notify_server")
@pytest.mark.parametrize(
    "error",
    {UpnpConnectionError(), UpnpCommunicationError(), UpnpResponseError(status=400)},
)
async def test_upnp_failed_re_subscribe_events(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    remotews: Mock,
    dmr_device: Mock,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    """Test for Upnp event feedback."""
    await setup_samsungtv_entry(hass, MOCK_ENTRY_WS)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert dmr_device.async_subscribe_services.call_count == 1
    assert dmr_device.async_unsubscribe_services.call_count == 0

    with (
        patch.object(
            remotews, "start_listening", side_effect=WebSocketException("Boom")
        ),
        patch.object(remotews, "is_alive", return_value=False),
    ):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert dmr_device.async_subscribe_services.call_count == 1
    assert dmr_device.async_unsubscribe_services.call_count == 1

    with patch.object(dmr_device, "async_subscribe_services", side_effect=error):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert "Device rejected re-subscription" in caplog.text
