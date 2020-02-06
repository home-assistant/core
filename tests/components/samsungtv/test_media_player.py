"""Tests for samsungtv component."""
import asyncio
from datetime import timedelta
import logging
from unittest.mock import call, patch

from asynctest import mock
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
from homeassistant.components.samsungtv.const import DOMAIN as SAMSUNGTV_DOMAIN
from homeassistant.components.samsungtv.media_player import (
    CONF_TIMEOUT,
    SUPPORT_SAMSUNGTV,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    CONF_BROADCAST_ADDRESS,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PLATFORM,
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
    STATE_UNKNOWN,
)
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.fake"
MOCK_CONFIG = {
    DOMAIN: {
        CONF_PLATFORM: SAMSUNGTV_DOMAIN,
        CONF_HOST: "fake",
        CONF_NAME: "fake",
        CONF_PORT: 8001,
        CONF_TIMEOUT: 10,
        CONF_MAC: "38:f9:d3:82:b4:f1",
    }
}

ENTITY_ID_BROADCAST = f"{DOMAIN}.fake_broadcast"
MOCK_CONFIG_BROADCAST = {
    DOMAIN: {
        CONF_PLATFORM: SAMSUNGTV_DOMAIN,
        CONF_HOST: "fake_broadcast",
        CONF_NAME: "fake_broadcast",
        CONF_PORT: 8001,
        CONF_TIMEOUT: 10,
        CONF_MAC: "38:f9:d3:82:b4:f1",
        CONF_BROADCAST_ADDRESS: "192.168.5.255",
    }
}

ENTITY_ID_NOMAC = f"{DOMAIN}.fake_nomac"
MOCK_CONFIG_NOMAC = {
    DOMAIN: {
        CONF_PLATFORM: SAMSUNGTV_DOMAIN,
        CONF_HOST: "fake_nomac",
        CONF_NAME: "fake_nomac",
        CONF_PORT: 55000,
        CONF_TIMEOUT: 10,
    }
}

ENTITY_ID_AUTO = f"{DOMAIN}.fake_auto"
MOCK_CONFIG_AUTO = {
    DOMAIN: {
        CONF_PLATFORM: SAMSUNGTV_DOMAIN,
        CONF_HOST: "fake_auto",
        CONF_NAME: "fake_auto",
    }
}

ENTITY_ID_DISCOVERY = f"{DOMAIN}.fake_discovery_fake_model"
MOCK_CONFIG_DISCOVERY = {
    "name": "fake_discovery",
    "model_name": "fake_model",
    "host": "fake_host",
    "udn": "fake_uuid",
}

ENTITY_ID_DISCOVERY_PREFIX = f"{DOMAIN}.fake_discovery_prefix_fake_model_prefix"
MOCK_CONFIG_DISCOVERY_PREFIX = {
    "name": "[TV]fake_discovery_prefix",
    "model_name": "fake_model_prefix",
    "host": "fake_host_prefix",
    "udn": "uuid:fake_uuid_prefix",
}

AUTODETECT_WEBSOCKET = {
    "name": "HomeAssistant",
    "description": "fake_auto",
    "id": "ha.component.samsung",
    "method": "websocket",
    "port": None,
    "host": "fake_auto",
    "timeout": 1,
}
AUTODETECT_LEGACY = {
    "name": "HomeAssistant",
    "description": "fake_auto",
    "id": "ha.component.samsung",
    "method": "legacy",
    "port": None,
    "host": "fake_auto",
    "timeout": 1,
}


@pytest.fixture(name="remote")
def remote_fixture():
    """Patch the samsungctl Remote."""
    with patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote"
    ) as remote_class, patch(
        "homeassistant.components.samsungtv.media_player.socket"
    ) as socket_class:
        remote = mock.Mock()
        remote_class.return_value = remote
        socket = mock.Mock()
        socket_class.return_value = socket
        yield remote


@pytest.fixture(name="wakeonlan")
def wakeonlan_fixture():
    """Patch the wakeonlan Remote."""
    with patch(
        "homeassistant.components.samsungtv.media_player.wakeonlan"
    ) as wakeonlan_module:
        yield wakeonlan_module


@pytest.fixture
def mock_now():
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


async def setup_samsungtv(hass, config):
    """Set up mock Samsung TV."""
    await async_setup_component(hass, "media_player", config)
    await hass.async_block_till_done()


async def test_setup_with_mac(hass, remote):
    """Test setup of platform."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert hass.states.get(ENTITY_ID)


async def test_setup_duplicate(hass, remote, caplog):
    """Test duplicate setup of platform."""
    DUPLICATE = {DOMAIN: [MOCK_CONFIG[DOMAIN], MOCK_CONFIG[DOMAIN]]}
    await setup_samsungtv(hass, DUPLICATE)
    assert "Ignoring duplicate Samsung TV fake" in caplog.text


async def test_setup_without_mac(hass, remote):
    """Test setup of platform."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOMAC)
    assert hass.states.get(ENTITY_ID_NOMAC)


async def test_setup_discovery(hass, remote):
    """Test setup of platform with discovery."""
    hass.async_create_task(
        async_load_platform(
            hass, DOMAIN, SAMSUNGTV_DOMAIN, MOCK_CONFIG_DISCOVERY, {DOMAIN: {}}
        )
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID_DISCOVERY)
    assert state
    assert state.name == "fake_discovery (fake_model)"
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    entry = entity_registry.async_get(ENTITY_ID_DISCOVERY)
    assert entry
    assert entry.unique_id == "fake_uuid"


async def test_setup_discovery_prefix(hass, remote):
    """Test setup of platform with discovery."""
    hass.async_create_task(
        async_load_platform(
            hass, DOMAIN, SAMSUNGTV_DOMAIN, MOCK_CONFIG_DISCOVERY_PREFIX, {DOMAIN: {}}
        )
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID_DISCOVERY_PREFIX)
    assert state
    assert state.name == "fake_discovery_prefix (fake_model_prefix)"
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    entry = entity_registry.async_get(ENTITY_ID_DISCOVERY_PREFIX)
    assert entry
    assert entry.unique_id == "fake_uuid_prefix"


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
    remote.control = mock.Mock(side_effect=OSError("Boom"))

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_send_key(hass, remote, wakeonlan):
    """Test for send key."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    # key and update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_VOLUP"), call("KEY")]
    assert state.state == STATE_ON


async def test_send_key_autodetect_websocket(hass, remote):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote"
    ) as remote, patch("homeassistant.components.samsungtv.media_player.socket"):
        await setup_samsungtv(hass, MOCK_CONFIG_AUTO)
        assert await hass.services.async_call(
            DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID_AUTO}, True
        )
        state = hass.states.get(ENTITY_ID_AUTO)
        assert remote.call_count == 1
        assert remote.call_args_list == [call(AUTODETECT_WEBSOCKET)]
        assert state.state == STATE_ON


async def test_send_key_autodetect_websocket_exception(hass, caplog):
    """Test for send key with autodetection of protocol."""
    caplog.set_level(logging.DEBUG)
    with patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote",
        side_effect=[exceptions.AccessDenied("Boom"), mock.DEFAULT],
    ) as remote, patch("homeassistant.components.samsungtv.media_player.socket"):
        await setup_samsungtv(hass, MOCK_CONFIG_AUTO)
        assert await hass.services.async_call(
            DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID_AUTO}, True
        )
        state = hass.states.get(ENTITY_ID_AUTO)
        # called 2 times because of the exception and the send key
        assert remote.call_count == 2
        assert remote.call_args_list == [
            call(AUTODETECT_WEBSOCKET),
            call(AUTODETECT_WEBSOCKET),
        ]
        assert state.state == STATE_ON
        assert "Found working config without connection: " in caplog.text
        assert "Failing config: " not in caplog.text


async def test_send_key_autodetect_legacy(hass, remote):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote",
        side_effect=[OSError("Boom"), mock.DEFAULT],
    ) as remote, patch("homeassistant.components.samsungtv.media_player.socket"):
        await setup_samsungtv(hass, MOCK_CONFIG_AUTO)
        assert await hass.services.async_call(
            DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID_AUTO}, True
        )
        state = hass.states.get(ENTITY_ID_AUTO)
        assert remote.call_count == 2
        assert remote.call_args_list == [
            call(AUTODETECT_WEBSOCKET),
            call(AUTODETECT_LEGACY),
        ]
        assert state.state == STATE_ON


async def test_send_key_autodetect_none(hass, remote):
    """Test for send key with autodetection of protocol."""
    with patch(
        "homeassistant.components.samsungtv.media_player.SamsungRemote",
        side_effect=OSError("Boom"),
    ) as remote, patch("homeassistant.components.samsungtv.media_player.socket"):
        await setup_samsungtv(hass, MOCK_CONFIG_AUTO)
        assert await hass.services.async_call(
            DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID_AUTO}, True
        )
        state = hass.states.get(ENTITY_ID_AUTO)
        # 4 calls because of retry
        assert remote.call_count == 4
        assert remote.call_args_list == [
            call(AUTODETECT_WEBSOCKET),
            call(AUTODETECT_LEGACY),
            call(AUTODETECT_WEBSOCKET),
            call(AUTODETECT_LEGACY),
        ]
        assert state.state == STATE_UNKNOWN


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
    assert remote.control.call_count == 3
    assert remote.control.call_args_list == [
        call("KEY_VOLUP"),
        call("KEY_VOLUP"),
        call("KEY"),
    ]
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
    assert state.state == STATE_OFF


async def test_name(hass, remote):
    """Test for name property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake"


async def test_state_with_mac(hass, remote, wakeonlan):
    """Test for state property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_state_without_mac(hass, remote):
    """Test for state property."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOMAC)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: ENTITY_ID_NOMAC}, True
    )
    state = hass.states.get(ENTITY_ID_NOMAC)
    assert state.state == STATE_ON
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID_NOMAC}, True
    )
    state = hass.states.get(ENTITY_ID_NOMAC)
    assert state.state == STATE_OFF


async def test_supported_features_with_mac(hass, remote):
    """Test for supported_features property."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_SAMSUNGTV | SUPPORT_TURN_ON
    )


async def test_supported_features_without_mac(hass, remote):
    """Test for supported_features property."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOMAC)
    state = hass.states.get(ENTITY_ID_NOMAC)
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


async def test_turn_off_legacy(hass, remote):
    """Test for turn_off."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOMAC)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID_NOMAC}, True
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
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_VOLUP"), call("KEY")]


async def test_volume_down(hass, remote):
    """Test for volume_down."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_VOLUME_DOWN, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_VOLDOWN"), call("KEY")]


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
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_MUTE"), call("KEY")]


async def test_media_play(hass, remote):
    """Test for media_play."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PLAY, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_PLAY"), call("KEY")]


async def test_media_pause(hass, remote):
    """Test for media_pause."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PAUSE, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_PAUSE"), call("KEY")]


async def test_media_next_track(hass, remote):
    """Test for media_next_track."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_NEXT_TRACK, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_CHUP"), call("KEY")]


async def test_media_previous_track(hass, remote):
    """Test for media_previous_track."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_CHDOWN"), call("KEY")]


async def test_turn_on_with_mac(hass, remote, wakeonlan):
    """Test turn on."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    # key and update called
    assert wakeonlan.send_magic_packet.call_count == 1
    assert wakeonlan.send_magic_packet.call_args_list == [
        call("38:f9:d3:82:b4:f1", ip_address="255.255.255.255")
    ]


async def test_turn_on_with_mac_and_broadcast(hass, remote, wakeonlan):
    """Test turn on."""
    await setup_samsungtv(hass, MOCK_CONFIG_BROADCAST)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID_BROADCAST}, True
    )
    # key and update called
    assert wakeonlan.send_magic_packet.call_count == 1
    assert wakeonlan.send_magic_packet.call_args_list == [
        call("38:f9:d3:82:b4:f1", ip_address="192.168.5.255")
    ]


async def test_turn_on_without_mac(hass, remote):
    """Test turn on."""
    await setup_samsungtv(hass, MOCK_CONFIG_NOMAC)
    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID_NOMAC}, True
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
        assert remote.control.call_count == 5
        assert remote.control.call_args_list == [
            call("KEY_5"),
            call("KEY_7"),
            call("KEY_6"),
            call("KEY_ENTER"),
            call("KEY"),
        ]
        assert len(sleeps) == 3


async def test_play_media_invalid_type(hass, remote):
    """Test for play_media with invalid media type."""
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
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY")]


async def test_play_media_channel_as_string(hass, remote):
    """Test for play_media with invalid channel as string."""
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
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY")]


async def test_play_media_channel_as_non_positive(hass, remote):
    """Test for play_media with invalid channel as non positive integer."""
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
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY")]


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
    assert remote.control.call_count == 2
    assert remote.control.call_args_list == [call("KEY_HDMI"), call("KEY")]


async def test_select_source_invalid_source(hass, remote):
    """Test for select_source with invalid source."""
    await setup_samsungtv(hass, MOCK_CONFIG)
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "INVALID"},
        True,
    )
    # only update called
    assert remote.control.call_count == 1
    assert remote.control.call_args_list == [call("KEY")]
