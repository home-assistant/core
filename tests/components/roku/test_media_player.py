"""Tests for the Roku Media Player platform."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from rokuecp import (
    Device as RokuDevice,
    RokuConnectionError,
    RokuConnectionTimeoutError,
    RokuError,
)
from syrupy import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    MediaClass,
    MediaType,
)
from homeassistant.components.roku.const import (
    ATTR_CONTENT_ID,
    ATTR_FORMAT,
    ATTR_KEYWORD,
    ATTR_MEDIA_TYPE,
    DEFAULT_PLAY_MEDIA_APP_ID,
    DOMAIN,
    SERVICE_SEARCH,
)
from homeassistant.components.stream import FORMAT_CONTENT_TYPE, HLS_PROVIDER
from homeassistant.components.websocket_api import TYPE_RESULT
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
    STATE_IDLE,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.typing import WebSocketGenerator

MAIN_ENTITY_ID = f"{MP_DOMAIN}.my_roku_3"
TV_ENTITY_ID = f"{MP_DOMAIN}.58_onn_roku_tv"


@pytest.mark.parametrize(
    "mock_device",
    [
        "roku3",
        "roku3-idle",
        "roku3-app",
        "roku3-screensaver",
        "roku3-media-paused",
        "roku3-media-playing",
        "rokutv-7820x",
    ],
    indirect=True,
)
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_device: RokuDevice,
    mock_roku: MagicMock,
) -> None:
    """Test the Roku media player entities."""
    with patch("homeassistant.components.roku.PLATFORMS", [Platform.MEDIA_PLAYER]):
        await setup_integration(hass, mock_config_entry, mock_device)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "error",
    [RokuConnectionTimeoutError, RokuConnectionError, RokuError],
)
async def test_availability(
    hass: HomeAssistant,
    mock_roku: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    error: RokuError,
) -> None:
    """Test entity availability."""
    now = dt_util.utcnow()
    future = now + timedelta(minutes=1)

    mock_config_entry.add_to_hass(hass)
    freezer.move_to(now)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.move_to(future)
    mock_roku.update.side_effect = error
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert hass.states.get(MAIN_ENTITY_ID).state == STATE_UNAVAILABLE

    future += timedelta(minutes=1)
    freezer.move_to(future)
    mock_roku.update.side_effect = None
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert hass.states.get(MAIN_ENTITY_ID).state == STATE_IDLE


async def test_services(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_roku: MagicMock,
) -> None:
    """Test the different media player services."""
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: MAIN_ENTITY_ID}, blocking=True
    )

    assert mock_roku.remote.call_count == 1
    mock_roku.remote.assert_called_with("poweroff")

    await hass.services.async_call(
        MP_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: MAIN_ENTITY_ID}, blocking=True
    )

    assert mock_roku.remote.call_count == 2
    mock_roku.remote.assert_called_with("poweron")

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
        blocking=True,
    )

    assert mock_roku.remote.call_count == 3
    mock_roku.remote.assert_called_with("play")

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
        blocking=True,
    )

    assert mock_roku.remote.call_count == 4
    mock_roku.remote.assert_called_with("play")

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_MEDIA_PLAY_PAUSE,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
        blocking=True,
    )

    assert mock_roku.remote.call_count == 5
    mock_roku.remote.assert_called_with("play")

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_MEDIA_NEXT_TRACK,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
        blocking=True,
    )

    assert mock_roku.remote.call_count == 6
    mock_roku.remote.assert_called_with("forward")

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
        blocking=True,
    )

    assert mock_roku.remote.call_count == 7
    mock_roku.remote.assert_called_with("reverse")

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_INPUT_SOURCE: "Home"},
        blocking=True,
    )

    assert mock_roku.remote.call_count == 8
    mock_roku.remote.assert_called_with("home")

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: MAIN_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.APP,
            ATTR_MEDIA_CONTENT_ID: "11",
        },
        blocking=True,
    )

    assert mock_roku.launch.call_count == 1
    mock_roku.launch.assert_called_with("11", {})

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: MAIN_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.APP,
            ATTR_MEDIA_CONTENT_ID: "291097",
            ATTR_MEDIA_EXTRA: {
                ATTR_MEDIA_TYPE: "movie",
                ATTR_CONTENT_ID: "8e06a8b7-d667-4e31-939d-f40a6dd78a88",
            },
        },
        blocking=True,
    )

    assert mock_roku.launch.call_count == 2
    mock_roku.launch.assert_called_with(
        "291097",
        {
            "contentID": "8e06a8b7-d667-4e31-939d-f40a6dd78a88",
            "mediaType": "movie",
        },
    )

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_INPUT_SOURCE: "Netflix"},
        blocking=True,
    )

    assert mock_roku.launch.call_count == 3
    mock_roku.launch.assert_called_with("12")

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_INPUT_SOURCE: 12},
        blocking=True,
    )

    assert mock_roku.launch.call_count == 4
    mock_roku.launch.assert_called_with("12")


async def test_services_play_media(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_roku: MagicMock,
) -> None:
    """Test the media player services related to playing media."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: MAIN_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: "blah",
            ATTR_MEDIA_CONTENT_ID: "https://localhost/media.m4a",
            ATTR_MEDIA_EXTRA: {
                ATTR_NAME: "Test",
            },
        },
        blocking=True,
    )

    assert mock_roku.launch.call_count == 0

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: MAIN_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "https://localhost/media.m4a",
            ATTR_MEDIA_EXTRA: {ATTR_FORMAT: "blah"},
        },
        blocking=True,
    )

    assert mock_roku.launch.call_count == 0


@pytest.mark.parametrize(
    ("content_type", "content_id", "resolved_name", "resolved_format"),
    [
        (MediaType.URL, "http://localhost/media.m4a", "media.m4a", "m4a"),
        (MediaType.MUSIC, "http://localhost/media.m4a", "media.m4a", "m4a"),
        (MediaType.MUSIC, "http://localhost/media.mka", "media.mka", "mka"),
        (
            MediaType.MUSIC,
            "http://localhost/api/tts_proxy/generated.mp3",
            "Text to Speech",
            "mp3",
        ),
    ],
)
async def test_services_play_media_audio(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_roku: MagicMock,
    content_type: str,
    content_id: str,
    resolved_name: str,
    resolved_format: str,
) -> None:
    """Test the media player services related to playing media."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: MAIN_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: content_type,
            ATTR_MEDIA_CONTENT_ID: content_id,
        },
        blocking=True,
    )
    mock_roku.launch.assert_called_once_with(
        DEFAULT_PLAY_MEDIA_APP_ID,
        {
            "u": content_id,
            "t": "a",
            "songName": resolved_name,
            "songFormat": resolved_format,
            "artistName": "Home Assistant",
        },
    )


@pytest.mark.parametrize(
    ("content_type", "content_id", "resolved_name", "resolved_format"),
    [
        (MediaType.URL, "http://localhost/media.mp4", "media.mp4", "mp4"),
        (MediaType.VIDEO, "http://localhost/media.m4v", "media.m4v", "mp4"),
        (MediaType.VIDEO, "http://localhost/media.mov", "media.mov", "mp4"),
        (MediaType.VIDEO, "http://localhost/media.mkv", "media.mkv", "mkv"),
        (MediaType.VIDEO, "http://localhost/media.mks", "media.mks", "mks"),
        (MediaType.VIDEO, "http://localhost/media.m3u8", "media.m3u8", "hls"),
        (MediaType.VIDEO, "http://localhost/media.dash", "media.dash", "dash"),
        (MediaType.VIDEO, "http://localhost/media.mpd", "media.mpd", "dash"),
        (MediaType.VIDEO, "http://localhost/media.ism/manifest", "media.ism", "ism"),
    ],
)
async def test_services_play_media_video(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_roku: MagicMock,
    content_type: str,
    content_id: str,
    resolved_name: str,
    resolved_format: str,
) -> None:
    """Test the media player services related to playing media."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: MAIN_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: content_type,
            ATTR_MEDIA_CONTENT_ID: content_id,
        },
        blocking=True,
    )
    mock_roku.launch.assert_called_once_with(
        DEFAULT_PLAY_MEDIA_APP_ID,
        {
            "u": content_id,
            "t": "v",
            "videoName": resolved_name,
            "videoFormat": resolved_format,
        },
    )


async def test_services_camera_play_stream(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_roku: MagicMock,
) -> None:
    """Test the media player services related to playing camera stream."""
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

    assert mock_roku.launch.call_count == 1
    mock_roku.launch.assert_called_with(
        DEFAULT_PLAY_MEDIA_APP_ID,
        {
            "u": "https://awesome.tld/api/hls/api_token/master_playlist.m3u8",
            "t": "v",
            "videoName": "Camera Stream",
            "videoFormat": "hls",
        },
    )


async def test_services_play_media_local_source(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_roku: MagicMock,
) -> None:
    """Test the media player services related to playing media."""
    local_media = hass.config.path("media")
    await async_process_ha_core_config(
        hass, {"media_dirs": {"local": local_media, "recordings": local_media}}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "media_source", {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: MAIN_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: "video/mp4",
            ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4",
        },
        blocking=True,
    )

    assert mock_roku.launch.call_count == 1
    assert mock_roku.launch.call_args
    call_args = mock_roku.launch.call_args.args
    assert call_args[0] == DEFAULT_PLAY_MEDIA_APP_ID
    assert "u" in call_args[1]
    assert "/local/Epic%20Sax%20Guy%2010%20Hours.mp4?authSig=" in call_args[1]["u"]
    assert "t" in call_args[1]
    assert call_args[1]["t"] == "v"
    assert "videoFormat" in call_args[1]
    assert call_args[1]["videoFormat"] == "mp4"
    assert "videoName" in call_args[1]
    assert (
        call_args[1]["videoName"]
        == "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4"
    )


@pytest.mark.parametrize("mock_device", ["rokutv-7820x"], indirect=True)
async def test_tv_services(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_roku: MagicMock,
) -> None:
    """Test the media player services related to Roku TV."""
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: TV_ENTITY_ID}, blocking=True
    )

    assert mock_roku.remote.call_count == 1
    mock_roku.remote.assert_called_with("volume_up")

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: TV_ENTITY_ID},
        blocking=True,
    )

    assert mock_roku.remote.call_count == 2
    mock_roku.remote.assert_called_with("volume_down")

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: TV_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )

    assert mock_roku.remote.call_count == 3
    mock_roku.remote.assert_called_with("volume_mute")

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: TV_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
            ATTR_MEDIA_CONTENT_ID: "55",
        },
        blocking=True,
    )

    assert mock_roku.tune.call_count == 1
    mock_roku.tune.assert_called_with("55")


async def test_media_browse(
    hass: HomeAssistant,
    init_integration,
    mock_roku,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test browsing media."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": MAIN_ENTITY_ID,
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert msg["result"]
    assert msg["result"]["title"] == "Apps"
    assert msg["result"]["media_class"] == MediaClass.DIRECTORY
    assert msg["result"]["media_content_type"] == MediaType.APPS
    assert msg["result"]["children_media_class"] == MediaClass.APP
    assert msg["result"]["can_expand"]
    assert not msg["result"]["can_play"]
    assert len(msg["result"]["children"]) == 8
    assert msg["result"]["children_media_class"] == MediaClass.APP

    assert msg["result"]["children"][0]["title"] == "Roku Channel Store"
    assert msg["result"]["children"][0]["media_content_type"] == MediaType.APP
    assert msg["result"]["children"][0]["media_content_id"] == "11"
    assert (
        msg["result"]["children"][0]["thumbnail"]
        == "http://192.168.1.160:8060/query/icon/11"
    )
    assert msg["result"]["children"][0]["can_play"]

    # test invalid media type
    await client.send_json(
        {
            "id": 2,
            "type": "media_player/browse_media",
            "entity_id": MAIN_ENTITY_ID,
            "media_content_type": "invalid",
            "media_content_id": "invalid",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 2
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]


async def test_media_browse_internal(
    hass: HomeAssistant,
    init_integration,
    mock_roku,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test browsing media with internal url."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    assert hass.config.internal_url == "http://example.local:8123"

    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.helpers.network._get_request_host", return_value="example.local"
    ):
        await client.send_json(
            {
                "id": 1,
                "type": "media_player/browse_media",
                "entity_id": MAIN_ENTITY_ID,
                "media_content_type": MediaType.APPS,
                "media_content_id": "apps",
            }
        )

        msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert msg["result"]
    assert msg["result"]["title"] == "Apps"
    assert msg["result"]["media_class"] == MediaClass.DIRECTORY
    assert msg["result"]["media_content_type"] == MediaType.APPS
    assert msg["result"]["children_media_class"] == MediaClass.APP
    assert msg["result"]["can_expand"]
    assert not msg["result"]["can_play"]
    assert len(msg["result"]["children"]) == 8
    assert msg["result"]["children_media_class"] == MediaClass.APP

    assert msg["result"]["children"][0]["title"] == "Roku Channel Store"
    assert msg["result"]["children"][0]["media_content_type"] == MediaType.APP
    assert msg["result"]["children"][0]["media_content_id"] == "11"
    assert "/query/icon/11" in msg["result"]["children"][0]["thumbnail"]
    assert msg["result"]["children"][0]["can_play"]


async def test_media_browse_local_source(
    hass: HomeAssistant,
    init_integration,
    mock_roku,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test browsing local media source."""
    local_media = hass.config.path("media")
    await async_process_ha_core_config(
        hass, {"media_dirs": {"local": local_media, "recordings": local_media}}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "media_source", {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": MAIN_ENTITY_ID,
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert msg["result"]
    assert msg["result"]["title"] == "Roku"
    assert msg["result"]["media_class"] == MediaClass.DIRECTORY
    assert msg["result"]["media_content_type"] == "root"
    assert msg["result"]["can_expand"]
    assert not msg["result"]["can_play"]
    assert len(msg["result"]["children"]) == 2

    assert msg["result"]["children"][0]["title"] == "Apps"
    assert msg["result"]["children"][0]["media_content_type"] == MediaType.APPS

    assert msg["result"]["children"][1]["title"] == "My media"
    assert msg["result"]["children"][1]["media_class"] == MediaClass.DIRECTORY
    assert msg["result"]["children"][1]["media_content_type"] is None
    assert (
        msg["result"]["children"][1]["media_content_id"]
        == "media-source://media_source"
    )
    assert not msg["result"]["children"][1]["can_play"]
    assert msg["result"]["children"][1]["can_expand"]

    # test local media
    await client.send_json(
        {
            "id": 2,
            "type": "media_player/browse_media",
            "entity_id": MAIN_ENTITY_ID,
            "media_content_type": "",
            "media_content_id": "media-source://media_source",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 2
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert msg["result"]
    assert msg["result"]["title"] == "My media"
    assert msg["result"]["media_class"] == MediaClass.DIRECTORY
    assert msg["result"]["media_content_type"] is None
    assert len(msg["result"]["children"]) == 2

    assert msg["result"]["children"][0]["title"] == "media"
    assert msg["result"]["children"][0]["media_content_type"] == ""
    assert (
        msg["result"]["children"][0]["media_content_id"]
        == "media-source://media_source/local/."
    )

    assert msg["result"]["children"][1]["title"] == "media"
    assert msg["result"]["children"][1]["media_content_type"] == ""
    assert (
        msg["result"]["children"][1]["media_content_id"]
        == "media-source://media_source/recordings/."
    )

    # test local media directory
    await client.send_json(
        {
            "id": 3,
            "type": "media_player/browse_media",
            "entity_id": MAIN_ENTITY_ID,
            "media_content_type": "",
            "media_content_id": "media-source://media_source/local/.",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 3
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert msg["result"]["title"] == "media"
    assert msg["result"]["media_class"] == MediaClass.DIRECTORY
    assert msg["result"]["media_content_type"] == ""
    assert len(msg["result"]["children"]) == 2

    assert msg["result"]["children"][0]["title"] == "Epic Sax Guy 10 Hours.mp4"
    assert msg["result"]["children"][0]["media_class"] == MediaClass.VIDEO
    assert msg["result"]["children"][0]["media_content_type"] == "video/mp4"
    assert (
        msg["result"]["children"][0]["media_content_id"]
        == "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4"
    )


@pytest.mark.parametrize("mock_device", ["rokutv-7820x"], indirect=True)
async def test_tv_media_browse(
    hass: HomeAssistant,
    init_integration,
    mock_roku,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test browsing media."""
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
    assert msg["result"]["title"] == "Roku"
    assert msg["result"]["media_class"] == MediaClass.DIRECTORY
    assert msg["result"]["media_content_type"] == "root"
    assert msg["result"]["can_expand"]
    assert not msg["result"]["can_play"]
    assert len(msg["result"]["children"]) == 2

    # test apps
    await client.send_json(
        {
            "id": 2,
            "type": "media_player/browse_media",
            "entity_id": TV_ENTITY_ID,
            "media_content_type": MediaType.APPS,
            "media_content_id": "apps",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 2
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert msg["result"]
    assert msg["result"]["title"] == "Apps"
    assert msg["result"]["media_class"] == MediaClass.DIRECTORY
    assert msg["result"]["media_content_type"] == MediaType.APPS
    assert msg["result"]["children_media_class"] == MediaClass.APP
    assert msg["result"]["can_expand"]
    assert not msg["result"]["can_play"]
    assert len(msg["result"]["children"]) == 11
    assert msg["result"]["children_media_class"] == MediaClass.APP

    assert msg["result"]["children"][0]["title"] == "Satellite TV"
    assert msg["result"]["children"][0]["media_content_type"] == MediaType.APP
    assert msg["result"]["children"][0]["media_content_id"] == "tvinput.hdmi2"
    assert (
        msg["result"]["children"][0]["thumbnail"]
        == "http://192.168.1.160:8060/query/icon/tvinput.hdmi2"
    )
    assert msg["result"]["children"][0]["can_play"]

    assert msg["result"]["children"][3]["title"] == "Roku Channel Store"
    assert msg["result"]["children"][3]["media_content_type"] == MediaType.APP
    assert msg["result"]["children"][3]["media_content_id"] == "11"
    assert (
        msg["result"]["children"][3]["thumbnail"]
        == "http://192.168.1.160:8060/query/icon/11"
    )
    assert msg["result"]["children"][3]["can_play"]

    # test channels
    await client.send_json(
        {
            "id": 3,
            "type": "media_player/browse_media",
            "entity_id": TV_ENTITY_ID,
            "media_content_type": MediaType.CHANNELS,
            "media_content_id": "channels",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 3
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert msg["result"]
    assert msg["result"]["title"] == "TV Channels"
    assert msg["result"]["media_class"] == MediaClass.DIRECTORY
    assert msg["result"]["media_content_type"] == MediaType.CHANNELS
    assert msg["result"]["children_media_class"] == MediaClass.CHANNEL
    assert msg["result"]["can_expand"]
    assert not msg["result"]["can_play"]
    assert len(msg["result"]["children"]) == 4
    assert msg["result"]["children_media_class"] == MediaClass.CHANNEL

    assert msg["result"]["children"][0]["title"] == "WhatsOn (1.1)"
    assert msg["result"]["children"][0]["media_content_type"] == MediaType.CHANNEL
    assert msg["result"]["children"][0]["media_content_id"] == "1.1"
    assert msg["result"]["children"][0]["can_play"]


async def test_integration_services(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_roku: MagicMock,
) -> None:
    """Test integration services."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_KEYWORD: "Space Jam"},
        blocking=True,
    )
    mock_roku.search.assert_called_once_with("Space Jam")
