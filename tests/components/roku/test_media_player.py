"""Tests for the Roku Media Player platform."""
from datetime import timedelta
from unittest.mock import patch

from rokuecp import RokuError

from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.components.media_player.const import (
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    MEDIA_CLASS_APP,
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_APPS,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_CHANNELS,
    MEDIA_TYPE_URL,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.components.roku.const import (
    ATTR_CONTENT_ID,
    ATTR_FORMAT,
    ATTR_KEYWORD,
    ATTR_MEDIA_TYPE,
    DOMAIN,
    SERVICE_SEARCH,
)
from homeassistant.components.stream.const import FORMAT_CONTENT_TYPE, HLS_PROVIDER
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
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
    STATE_HOME,
    STATE_IDLE,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.roku import NAME_ROKUTV, UPNP_SERIAL, setup_integration
from tests.test_util.aiohttp import AiohttpClientMocker

MAIN_ENTITY_ID = f"{MP_DOMAIN}.my_roku_3"
TV_ENTITY_ID = f"{MP_DOMAIN}.58_onn_roku_tv"

TV_HOST = "192.168.1.161"
TV_LOCATION = "Living room"
TV_MANUFACTURER = "Onn"
TV_MODEL = "100005844"
TV_SERIAL = "YN00H5555555"
TV_SW_VERSION = "9.2.0"


async def test_setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test setup with basic config."""
    await setup_integration(hass, aioclient_mock)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get(MAIN_ENTITY_ID)
    entry = entity_registry.async_get(MAIN_ENTITY_ID)

    assert state
    assert entry
    assert entry.original_device_class is MediaPlayerDeviceClass.RECEIVER
    assert entry.unique_id == UPNP_SERIAL

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, UPNP_SERIAL)}
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, "b0:a7:37:96:4d:fb"),
        (dr.CONNECTION_NETWORK_MAC, "b0:a7:37:96:4d:fa"),
    }
    assert device_entry.manufacturer == "Roku"
    assert device_entry.model == "Roku 3"
    assert device_entry.name == "My Roku 3"
    assert device_entry.entry_type is None
    assert device_entry.hw_version == "4200X"
    assert device_entry.sw_version == "7.5.0"


async def test_idle_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with idle device."""
    await setup_integration(hass, aioclient_mock, power=False)

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state
    assert state.state == STATE_STANDBY


async def test_tv_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test Roku TV setup."""
    await setup_integration(
        hass,
        aioclient_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get(TV_ENTITY_ID)
    entry = entity_registry.async_get(TV_ENTITY_ID)

    assert state
    assert entry
    assert entry.original_device_class is MediaPlayerDeviceClass.TV
    assert entry.unique_id == TV_SERIAL

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, TV_SERIAL)}
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, "d8:13:99:f8:b0:c6"),
        (dr.CONNECTION_NETWORK_MAC, "d4:3a:2e:07:fd:cb"),
    }
    assert device_entry.manufacturer == TV_MANUFACTURER
    assert device_entry.model == TV_MODEL
    assert device_entry.name == '58" Onn Roku TV'
    assert device_entry.entry_type is None
    assert device_entry.hw_version == "7820X"
    assert device_entry.sw_version == TV_SW_VERSION


async def test_availability(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test entity availability."""
    now = dt_util.utcnow()
    future = now + timedelta(minutes=1)

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass, aioclient_mock)

    with patch(
        "homeassistant.components.roku.coordinator.Roku.update", side_effect=RokuError
    ), patch("homeassistant.util.dt.utcnow", return_value=future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert hass.states.get(MAIN_ENTITY_ID).state == STATE_UNAVAILABLE

    future += timedelta(minutes=1)

    with patch("homeassistant.util.dt.utcnow", return_value=future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert hass.states.get(MAIN_ENTITY_ID).state == STATE_HOME


async def test_supported_features(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test supported features."""
    await setup_integration(hass, aioclient_mock)

    # Features supported for Rokus
    state = hass.states.get(MAIN_ENTITY_ID)
    assert (
        SUPPORT_PREVIOUS_TRACK
        | SUPPORT_NEXT_TRACK
        | SUPPORT_VOLUME_STEP
        | SUPPORT_VOLUME_MUTE
        | SUPPORT_SELECT_SOURCE
        | SUPPORT_PAUSE
        | SUPPORT_PLAY
        | SUPPORT_PLAY_MEDIA
        | SUPPORT_TURN_ON
        | SUPPORT_TURN_OFF
        | SUPPORT_BROWSE_MEDIA
        == state.attributes.get("supported_features")
    )


async def test_tv_supported_features(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test supported features for Roku TV."""
    await setup_integration(
        hass,
        aioclient_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    state = hass.states.get(TV_ENTITY_ID)
    assert (
        SUPPORT_PREVIOUS_TRACK
        | SUPPORT_NEXT_TRACK
        | SUPPORT_VOLUME_STEP
        | SUPPORT_VOLUME_MUTE
        | SUPPORT_SELECT_SOURCE
        | SUPPORT_PAUSE
        | SUPPORT_PLAY
        | SUPPORT_PLAY_MEDIA
        | SUPPORT_TURN_ON
        | SUPPORT_TURN_OFF
        | SUPPORT_BROWSE_MEDIA
        == state.attributes.get("supported_features")
    )


async def test_attributes(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test attributes."""
    await setup_integration(hass, aioclient_mock)

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_HOME

    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) is None
    assert state.attributes.get(ATTR_APP_ID) is None
    assert state.attributes.get(ATTR_APP_NAME) == "Roku"
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "Roku"


async def test_attributes_app(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test attributes for app."""
    await setup_integration(hass, aioclient_mock, app="netflix")

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_ON

    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) == MEDIA_TYPE_APP
    assert state.attributes.get(ATTR_APP_ID) == "12"
    assert state.attributes.get(ATTR_APP_NAME) == "Netflix"
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "Netflix"


async def test_attributes_app_media_playing(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test attributes for app with playing media."""
    await setup_integration(hass, aioclient_mock, app="pluto", media_state="play")

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_PLAYING

    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) == MEDIA_TYPE_APP
    assert state.attributes.get(ATTR_MEDIA_DURATION) == 6496
    assert state.attributes.get(ATTR_MEDIA_POSITION) == 38
    assert state.attributes.get(ATTR_APP_ID) == "74519"
    assert state.attributes.get(ATTR_APP_NAME) == "Pluto TV - It's Free TV"
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "Pluto TV - It's Free TV"


async def test_attributes_app_media_paused(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test attributes for app with paused media."""
    await setup_integration(hass, aioclient_mock, app="pluto", media_state="pause")

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_PAUSED

    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) == MEDIA_TYPE_APP
    assert state.attributes.get(ATTR_MEDIA_DURATION) == 6496
    assert state.attributes.get(ATTR_MEDIA_POSITION) == 313
    assert state.attributes.get(ATTR_APP_ID) == "74519"
    assert state.attributes.get(ATTR_APP_NAME) == "Pluto TV - It's Free TV"
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "Pluto TV - It's Free TV"


async def test_attributes_screensaver(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test attributes for app with screensaver."""
    await setup_integration(hass, aioclient_mock, app="screensaver")

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_IDLE

    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) is None
    assert state.attributes.get(ATTR_APP_ID) is None
    assert state.attributes.get(ATTR_APP_NAME) == "Roku"
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "Roku"


async def test_tv_attributes(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test attributes for Roku TV."""
    await setup_integration(
        hass,
        aioclient_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    state = hass.states.get(TV_ENTITY_ID)
    assert state.state == STATE_ON

    assert state.attributes.get(ATTR_APP_ID) == "tvinput.dtv"
    assert state.attributes.get(ATTR_APP_NAME) == "Antenna TV"
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "Antenna TV"
    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) == MEDIA_TYPE_CHANNEL
    assert state.attributes.get(ATTR_MEDIA_CHANNEL) == "getTV (14.3)"
    assert state.attributes.get(ATTR_MEDIA_TITLE) == "Airwolf"


async def test_tv_device_registry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test device registered for Roku TV in the device registry."""
    await setup_integration(
        hass,
        aioclient_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(identifiers={(DOMAIN, TV_SERIAL)})

    assert reg_device.model == TV_MODEL
    assert reg_device.sw_version == TV_SW_VERSION
    assert reg_device.manufacturer == TV_MANUFACTURER
    assert reg_device.suggested_area == TV_LOCATION
    assert reg_device.name == NAME_ROKUTV


async def test_services(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the different media player services."""
    await setup_integration(hass, aioclient_mock)

    with patch("homeassistant.components.roku.coordinator.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: MAIN_ENTITY_ID}, blocking=True
        )

        remote_mock.assert_called_once_with("poweroff")

    with patch("homeassistant.components.roku.coordinator.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: MAIN_ENTITY_ID}, blocking=True
        )

        remote_mock.assert_called_once_with("poweron")

    with patch("homeassistant.components.roku.coordinator.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_PAUSE,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("play")

    with patch("homeassistant.components.roku.coordinator.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_PLAY,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("play")

    with patch("homeassistant.components.roku.coordinator.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_PLAY_PAUSE,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("play")

    with patch("homeassistant.components.roku.coordinator.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("forward")

    with patch("homeassistant.components.roku.coordinator.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("reverse")

    with patch("homeassistant.components.roku.coordinator.Roku.launch") as launch_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: MAIN_ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_APP,
                ATTR_MEDIA_CONTENT_ID: "11",
            },
            blocking=True,
        )

        launch_mock.assert_called_once_with("11", {})

    with patch("homeassistant.components.roku.coordinator.Roku.launch") as launch_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: MAIN_ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_APP,
                ATTR_MEDIA_CONTENT_ID: "291097",
                ATTR_MEDIA_EXTRA: {
                    ATTR_MEDIA_TYPE: "movie",
                    ATTR_CONTENT_ID: "8e06a8b7-d667-4e31-939d-f40a6dd78a88",
                },
            },
            blocking=True,
        )

        launch_mock.assert_called_once_with(
            "291097",
            {
                "contentID": "8e06a8b7-d667-4e31-939d-f40a6dd78a88",
                "MediaType": "movie",
            },
        )

    with patch("homeassistant.components.roku.coordinator.Roku.play_video") as pv_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: MAIN_ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_URL,
                ATTR_MEDIA_CONTENT_ID: "https://awesome.tld/media.mp4",
                ATTR_MEDIA_EXTRA: {
                    ATTR_NAME: "Sent from HA",
                    ATTR_FORMAT: "mp4",
                },
            },
            blocking=True,
        )

        pv_mock.assert_called_once_with(
            "https://awesome.tld/media.mp4",
            {
                "videoName": "Sent from HA",
                "videoFormat": "mp4",
            },
        )

    with patch("homeassistant.components.roku.coordinator.Roku.play_video") as pv_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: MAIN_ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: FORMAT_CONTENT_TYPE[HLS_PROVIDER],
                ATTR_MEDIA_CONTENT_ID: "https://awesome.tld/api/hls/api_token/master_playlist.m3u8",
            },
            blocking=True,
        )

        pv_mock.assert_called_once_with(
            "https://awesome.tld/api/hls/api_token/master_playlist.m3u8",
            {
                "MediaType": "hls",
            },
        )

    with patch("homeassistant.components.roku.coordinator.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_INPUT_SOURCE: "Home"},
            blocking=True,
        )

        remote_mock.assert_called_once_with("home")

    with patch("homeassistant.components.roku.coordinator.Roku.launch") as launch_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_INPUT_SOURCE: "Netflix"},
            blocking=True,
        )

        launch_mock.assert_called_once_with("12")

    with patch("homeassistant.components.roku.coordinator.Roku.launch") as launch_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_INPUT_SOURCE: 12},
            blocking=True,
        )

        launch_mock.assert_called_once_with("12")


async def test_tv_services(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the media player services related to Roku TV."""
    await setup_integration(
        hass,
        aioclient_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    with patch("homeassistant.components.roku.coordinator.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: TV_ENTITY_ID}, blocking=True
        )

        remote_mock.assert_called_once_with("volume_up")

    with patch("homeassistant.components.roku.coordinator.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_DOWN,
            {ATTR_ENTITY_ID: TV_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("volume_down")

    with patch("homeassistant.components.roku.coordinator.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_MUTE,
            {ATTR_ENTITY_ID: TV_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
            blocking=True,
        )

        remote_mock.assert_called_once_with("volume_mute")

    with patch("homeassistant.components.roku.coordinator.Roku.tune") as tune_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: TV_ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_CHANNEL,
                ATTR_MEDIA_CONTENT_ID: "55",
            },
            blocking=True,
        )

        tune_mock.assert_called_once_with("55")


async def test_media_browse(hass, aioclient_mock, hass_ws_client):
    """Test browsing media."""
    await setup_integration(
        hass,
        aioclient_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": TV_ENTITY_ID,
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert msg["result"]
    assert msg["result"]["title"] == "Media Library"
    assert msg["result"]["media_class"] == MEDIA_CLASS_DIRECTORY
    assert msg["result"]["media_content_type"] == "library"
    assert msg["result"]["can_expand"]
    assert not msg["result"]["can_play"]
    assert len(msg["result"]["children"]) == 2

    # test apps
    await client.send_json(
        {
            "id": 2,
            "type": "media_player/browse_media",
            "entity_id": TV_ENTITY_ID,
            "media_content_type": MEDIA_TYPE_APPS,
            "media_content_id": "apps",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 2
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert msg["result"]
    assert msg["result"]["title"] == "Apps"
    assert msg["result"]["media_class"] == MEDIA_CLASS_DIRECTORY
    assert msg["result"]["media_content_type"] == MEDIA_TYPE_APPS
    assert msg["result"]["children_media_class"] == MEDIA_CLASS_APP
    assert msg["result"]["can_expand"]
    assert not msg["result"]["can_play"]
    assert len(msg["result"]["children"]) == 11
    assert msg["result"]["children_media_class"] == MEDIA_CLASS_APP

    assert msg["result"]["children"][0]["title"] == "Satellite TV"
    assert msg["result"]["children"][0]["media_content_type"] == MEDIA_TYPE_APP
    assert msg["result"]["children"][0]["media_content_id"] == "tvinput.hdmi2"
    assert (
        "/browse_media/app/tvinput.hdmi2" in msg["result"]["children"][0]["thumbnail"]
    )
    assert msg["result"]["children"][0]["can_play"]

    assert msg["result"]["children"][3]["title"] == "Roku Channel Store"
    assert msg["result"]["children"][3]["media_content_type"] == MEDIA_TYPE_APP
    assert msg["result"]["children"][3]["media_content_id"] == "11"
    assert "/browse_media/app/11" in msg["result"]["children"][3]["thumbnail"]
    assert msg["result"]["children"][3]["can_play"]

    # test channels
    await client.send_json(
        {
            "id": 3,
            "type": "media_player/browse_media",
            "entity_id": TV_ENTITY_ID,
            "media_content_type": MEDIA_TYPE_CHANNELS,
            "media_content_id": "channels",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 3
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert msg["result"]
    assert msg["result"]["title"] == "Channels"
    assert msg["result"]["media_class"] == MEDIA_CLASS_DIRECTORY
    assert msg["result"]["media_content_type"] == MEDIA_TYPE_CHANNELS
    assert msg["result"]["children_media_class"] == MEDIA_CLASS_CHANNEL
    assert msg["result"]["can_expand"]
    assert not msg["result"]["can_play"]
    assert len(msg["result"]["children"]) == 2
    assert msg["result"]["children_media_class"] == MEDIA_CLASS_CHANNEL

    assert msg["result"]["children"][0]["title"] == "WhatsOn"
    assert msg["result"]["children"][0]["media_content_type"] == MEDIA_TYPE_CHANNEL
    assert msg["result"]["children"][0]["media_content_id"] == "1.1"
    assert msg["result"]["children"][0]["can_play"]

    # test invalid media type
    await client.send_json(
        {
            "id": 4,
            "type": "media_player/browse_media",
            "entity_id": TV_ENTITY_ID,
            "media_content_type": "invalid",
            "media_content_id": "invalid",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 4
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]


async def test_media_browse_internal(hass, aioclient_mock, hass_ws_client):
    """Test browsing media with internal url."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    assert hass.config.internal_url == "http://example.local:8123"

    await setup_integration(
        hass,
        aioclient_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.helpers.network._get_request_host", return_value="example.local"
    ):
        await client.send_json(
            {
                "id": 2,
                "type": "media_player/browse_media",
                "entity_id": TV_ENTITY_ID,
                "media_content_type": MEDIA_TYPE_APPS,
                "media_content_id": "apps",
            }
        )

        msg = await client.receive_json()

    assert msg["id"] == 2
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert msg["result"]
    assert msg["result"]["title"] == "Apps"
    assert msg["result"]["media_class"] == MEDIA_CLASS_DIRECTORY
    assert msg["result"]["media_content_type"] == MEDIA_TYPE_APPS
    assert msg["result"]["children_media_class"] == MEDIA_CLASS_APP
    assert msg["result"]["can_expand"]
    assert not msg["result"]["can_play"]
    assert len(msg["result"]["children"]) == 11
    assert msg["result"]["children_media_class"] == MEDIA_CLASS_APP

    assert msg["result"]["children"][0]["title"] == "Satellite TV"
    assert msg["result"]["children"][0]["media_content_type"] == MEDIA_TYPE_APP
    assert msg["result"]["children"][0]["media_content_id"] == "tvinput.hdmi2"
    assert "/query/icon/tvinput.hdmi2" in msg["result"]["children"][0]["thumbnail"]
    assert msg["result"]["children"][0]["can_play"]

    assert msg["result"]["children"][3]["title"] == "Roku Channel Store"
    assert msg["result"]["children"][3]["media_content_type"] == MEDIA_TYPE_APP
    assert msg["result"]["children"][3]["media_content_id"] == "11"
    assert "/query/icon/11" in msg["result"]["children"][3]["thumbnail"]
    assert msg["result"]["children"][3]["can_play"]


async def test_integration_services(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test integration services."""
    await setup_integration(hass, aioclient_mock)

    with patch("homeassistant.components.roku.coordinator.Roku.search") as search_mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_KEYWORD: "Space Jam"},
            blocking=True,
        )
        search_mock.assert_called_once_with("Space Jam")
