"""Tests for Shelly media player platform."""

from copy import deepcopy
from unittest.mock import Mock

from aioshelly.const import MODEL_WALL_DISPLAY
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.media_player import (
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_PLAY_MEDIA,
    SERVICE_VOLUME_SET,
)
from homeassistant.components.shelly.media_player import (
    CONTENT_TYPE_AUDIO,
    CONTENT_TYPE_RADIO,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_PLAYING,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_registry import EntityRegistry

from . import init_integration, patch_platforms

from tests.typing import ClientSessionGenerator, WebSocketGenerator

ENTITY_ID = f"{MEDIA_PLAYER_DOMAIN}.test_name"

AUDIO_FILES = [
    {
        "album": "Album Placeholder",
        "artist": "Artist Placeholder",
        "duration": 106000,
        "filename": "track_alpha.mp3",
        "id": 16,
        "index": 0,
        "preview": "https://example.com/media/thumb?id=16&_t=track_alpha.mp3",
        "size": 3390000,
        "title": "Track Alpha",
        "track": 0,
        "type": "AUDIO",
        "valid": True,
        "year": 0,
    },
    {
        "album": "Album Placeholder",
        "artist": "Artist Placeholder",
        "duration": 138000,
        "filename": "track_beta.mp3",
        "id": 15,
        "index": 0,
        "preview": "https://example.com/media/thumb?id=15&_t=track_beta.mp3",
        "size": 4425000,
        "title": "Track Beta",
        "track": 0,
        "type": "AUDIO",
        "valid": True,
        "year": 0,
    },
    {
        "filename": "ringtone_gamma.mp3",
        "id": 17,
        "index": 0,
        "preview": "https://example.com/media/thumb?id=17&_t=ringtone_gamma.mp3",
        "size": 552000,
        "title": "Ringtone Gamma",
        "type": "RINGTONE",
        "valid": True,
    },
]

RADIO_STATIONS = [
    {
        "id": 0,
        "name": "Station Alpha",
        "country_code": "XX",
        "icon": "https://example.com/icons/alpha.png",
    },
    {
        "id": 1,
        "name": "Station Beta",
        "country_code": "XX",
        "icon": "https://example.com/icons/beta.png",
    },
    {
        "id": 2,
        "name": "Station Gamma",
        "country_code": "XX",
        "icon": "https://example.com/icons/gamma.png",
    },
    {
        "id": 3,
        "name": "Station Delta",
        "country_code": "XX",
        "icon": "https://example.com/icons/delta.png",
    },
]
STATUS_RADIO_STATION = {
    "playback": {
        "enable": True,
        "buffering": False,
        "volume": 5,
        "media_meta": {
            "thumb": "https://www.radio_station.pl/icon.png",
            "title": "Radio Station",
        },
        "media_type": "RADIO",
    },
}
STATUS_AUDIO_FILE = {
    "playback": {
        "buffering": False,
        "enable": True,
        "volume": 2,
        "media_meta": {
            "album": "Album Name",
            "artist": "Artist",
            "duration": 132415,
            "position": 64644,
            "thumb": "data:image/webp;base64,UklGRkAAAABXRUJQVlA4WAoAAAAQAAAAAAAAAAAAQUxQSAIAAAAAAFZQOCAYAAAAMAEAnQEqAQABAAFAJiWkAANwAP79NmgA",
            "title": "Title",
        },
        "media_type": "AUDIO",
    }
}


@pytest.fixture(autouse=True)
def fixture_platforms():
    """Limit platforms under test."""
    with patch_platforms([Platform.MEDIA_PLAYER]):
        yield


async def test_rpc_media_player(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a Shelly RPC media player."""
    status = deepcopy(mock_rpc_device.status)
    status["media"] = STATUS_RADIO_STATION
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    assert (state := hass.states.get(ENTITY_ID))
    assert state == snapshot(
        name=f"{ENTITY_ID}-state", exclude=props("entity_picture_local")
    )

    assert (entry := entity_registry.async_get(ENTITY_ID))
    assert entry == snapshot(name=f"{ENTITY_ID}-entry")

    monkeypatch.setitem(mock_rpc_device.status["media"]["playback"], "enable", False)
    monkeypatch.setitem(mock_rpc_device.status["media"]["playback"], "buffering", True)
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_BUFFERING


async def test_rpc_media_player_audio_file(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a Shelly RPC media player."""
    status = deepcopy(mock_rpc_device.status)
    status["media"] = STATUS_AUDIO_FILE
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_PLAYING
    assert state.attributes[ATTR_MEDIA_TITLE] == "Title"
    assert state.attributes[ATTR_MEDIA_ARTIST] == "Artist"
    assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == "Album Name"
    assert state.attributes[ATTR_MEDIA_DURATION] == 132
    assert state.attributes[ATTR_MEDIA_POSITION] == 64
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.2

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    monkeypatch.setitem(mock_rpc_device.status["media"]["playback"], "enable", False)
    mock_rpc_device.mock_update()

    mock_rpc_device.media_play_or_pause.assert_called_once()
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_IDLE

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    monkeypatch.setitem(mock_rpc_device.status["media"]["playback"], "enable", True)
    mock_rpc_device.mock_update()

    assert len(mock_rpc_device.media_play_or_pause.mock_calls) == 2
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_PLAYING

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    monkeypatch.setitem(mock_rpc_device.status["media"]["playback"], "enable", False)
    mock_rpc_device.mock_update()

    mock_rpc_device.media_stop.assert_called_once()
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_IDLE


async def test_rpc_media_player_actions(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a Shelly RPC media player."""
    status = deepcopy(mock_rpc_device.status)
    status["media"] = STATUS_AUDIO_FILE
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_NEXT_TRACK,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_rpc_device.media_next.assert_called_once()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_rpc_device.mock_update()

    mock_rpc_device.media_previous.assert_called_once()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )

    mock_rpc_device.media_set_volume.assert_called_once_with(5)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: CONTENT_TYPE_AUDIO,
            ATTR_MEDIA_CONTENT_ID: "12",
        },
        blocking=True,
    )

    mock_rpc_device.media_play_media.assert_called_once_with(12)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: CONTENT_TYPE_RADIO,
            ATTR_MEDIA_CONTENT_ID: "2",
        },
        blocking=True,
    )

    mock_rpc_device.media_play_radio_station.assert_called_once_with(2)


async def test_rpc_media_player_play_media_errors(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a Shelly RPC errors in play media method."""
    status = deepcopy(mock_rpc_device.status)
    status["media"] = STATUS_AUDIO_FILE
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    with pytest.raises(
        HomeAssistantError, match="Unsupported media ID for Shelly device: invalid"
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: CONTENT_TYPE_RADIO,
                ATTR_MEDIA_CONTENT_ID: "invalid",
            },
            blocking=True,
        )

    with pytest.raises(
        HomeAssistantError, match="Unsupported media type for Shelly device: invalid"
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: "invalid",
                ATTR_MEDIA_CONTENT_ID: "1",
            },
            blocking=True,
        )


async def test_get_image_http(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test get image via http command."""
    status = deepcopy(mock_rpc_device.status)
    status["media"] = STATUS_AUDIO_FILE
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    state = hass.states.get(ENTITY_ID)
    assert "entity_picture_local" not in state.attributes

    client = await hass_client_no_auth()

    resp = await client.get(state.attributes["entity_picture"])
    content = await resp.read()

    assert isinstance(content, bytes)


async def test_get_image_http_base64_decode_error(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test get image via http command base64 decode error."""
    status = deepcopy(mock_rpc_device.status)
    status["media"] = STATUS_AUDIO_FILE
    status["media"]["playback"]["media_meta"]["thumb"] = "data:image/webp;base64,0"
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    state = hass.states.get(ENTITY_ID)
    assert "entity_picture_local" not in state.attributes

    client = await hass_client_no_auth()

    resp = await client.get(state.attributes["entity_picture"])
    content = await resp.read()

    assert isinstance(content, bytes)


async def test_rpc_media_player_browse_media_root(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test Shelly media player browse media root."""
    status = deepcopy(mock_rpc_device.status)
    status["media"] = STATUS_AUDIO_FILE
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
        }
    )

    msg = await websocket_client.receive_json()

    assert msg["success"]
    assert msg["result"]["title"] == "Shelly"
    assert msg["result"]["media_class"] == "directory"
    assert msg["result"]["media_content_id"] == ""
    assert [child["title"] for child in msg["result"]["children"]] == [
        "Radio stations",
        "Audio files",
    ]
    assert [child["media_content_type"] for child in msg["result"]["children"]] == [
        CONTENT_TYPE_RADIO,
        CONTENT_TYPE_AUDIO,
    ]


async def test_rpc_media_player_browse_media_radio_stations(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test Shelly media player browse media radio stations."""
    status = deepcopy(mock_rpc_device.status)
    status["media"] = STATUS_RADIO_STATION
    monkeypatch.setattr(mock_rpc_device, "status", status)
    mock_rpc_device.media_list_radio_stations.return_value = RADIO_STATIONS

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": CONTENT_TYPE_RADIO,
            "media_content_id": CONTENT_TYPE_RADIO,
        }
    )

    msg = await websocket_client.receive_json()

    assert msg["success"]
    assert msg["result"]["title"] == "Radio stations"
    assert msg["result"]["media_class"] == "directory"
    assert msg["result"]["media_content_type"] == CONTENT_TYPE_RADIO
    assert [child["title"] for child in msg["result"]["children"]] == [
        station["name"] for station in RADIO_STATIONS
    ]
    assert [child["media_content_id"] for child in msg["result"]["children"]] == [
        str(station["id"]) for station in RADIO_STATIONS
    ]
    assert [child["thumbnail"] for child in msg["result"]["children"]] == [
        station["icon"] for station in RADIO_STATIONS
    ]


async def test_rpc_media_player_browse_media_audio_files(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test Shelly media player browse media audio files."""
    status = deepcopy(mock_rpc_device.status)
    status["media"] = STATUS_AUDIO_FILE
    monkeypatch.setattr(mock_rpc_device, "status", status)
    mock_rpc_device.media_list_media.return_value = AUDIO_FILES

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": CONTENT_TYPE_AUDIO,
            "media_content_id": CONTENT_TYPE_AUDIO,
        }
    )

    msg = await websocket_client.receive_json()

    assert msg["success"]
    assert msg["result"]["title"] == "Audio files"
    assert msg["result"]["media_class"] == "directory"
    assert msg["result"]["media_content_type"] == CONTENT_TYPE_AUDIO
    assert [child["title"] for child in msg["result"]["children"]] == [
        item["title"] for item in AUDIO_FILES if item["type"] == "AUDIO"
    ]
    assert [child["media_content_id"] for child in msg["result"]["children"]] == [
        str(item["id"]) for item in AUDIO_FILES if item["type"] == "AUDIO"
    ]
    assert [child["thumbnail"] for child in msg["result"]["children"]] == [
        item["preview"] for item in AUDIO_FILES if item["type"] == "AUDIO"
    ]


async def test_rpc_media_player_browse_media_unsupported_media_type(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test Shelly media player browse media returns unsupported media content type."""
    status = deepcopy(mock_rpc_device.status)
    status["media"] = STATUS_AUDIO_FILE
    monkeypatch.setattr(mock_rpc_device, "status", status)
    mock_rpc_device.media_list_media.return_value = AUDIO_FILES

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "invalid",
            "media_content_id": CONTENT_TYPE_AUDIO,
        }
    )

    msg = await websocket_client.receive_json()

    assert msg["error"]
    assert msg["error"]["code"] == "home_assistant_error"
    assert msg["error"]["message"] == (
        "Unsupported media content type for Shelly device: invalid"
    )


@pytest.mark.parametrize(
    ("side_effect", "expected_message"),
    [
        (
            DeviceConnectionError,
            "Device communication error occurred while calling action for media_player.test_name of Test name",
        ),
        (
            RpcCallError(999),
            "RPC call error occurred while calling action for media_player.test_name of Test name",
        ),
        (
            InvalidAuthError,
            "Authentication failed for Test name, please update your credentials",
        ),
    ],
)
async def test_rpc_media_player_browse_media_errors(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    hass_ws_client: WebSocketGenerator,
    side_effect: Exception,
    expected_message: str,
) -> None:
    """Test Shelly media player browse media returns errors."""
    status = deepcopy(mock_rpc_device.status)
    status["media"] = STATUS_AUDIO_FILE
    monkeypatch.setattr(mock_rpc_device, "status", status)
    mock_rpc_device.media_list_media.side_effect = side_effect

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": CONTENT_TYPE_AUDIO,
            "media_content_id": CONTENT_TYPE_AUDIO,
        }
    )

    msg = await websocket_client.receive_json()

    assert msg["error"]
    assert msg["error"]["code"] == "home_assistant_error"
    assert msg["error"]["message"] == expected_message


async def test_rpc_media_player_no_media_meta(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a Shelly RPC media player with no media metadata."""
    status = deepcopy(mock_rpc_device.status)
    status["media"] = STATUS_AUDIO_FILE
    status["media"]["playback"].pop("media_meta")
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_PLAYING
    assert state.attributes.get(ATTR_MEDIA_TITLE) is None
    assert state.attributes.get(ATTR_MEDIA_ARTIST) is None
    assert state.attributes.get(ATTR_MEDIA_ALBUM_NAME) is None
    assert state.attributes.get(ATTR_MEDIA_DURATION) is None
    assert state.attributes.get(ATTR_MEDIA_POSITION) is None
