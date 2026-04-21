"""Tests for Shelly media player platform."""

from copy import deepcopy
from unittest.mock import Mock

from aioshelly.const import MODEL_WALL_DISPLAY
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
    CONTENT_TYPE_LOCAL_AUDIO,
    CONTENT_TYPE_LOCAL_RADIO,
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

ENTITY_ID = f"{MEDIA_PLAYER_DOMAIN}.test_name"

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

    monkeypatch.setitem(mock_rpc_device.status["media"]["playback"], "enable", False)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_rpc_device.mock_update()

    mock_rpc_device.media_play_or_pause.assert_called_once()
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_IDLE

    monkeypatch.setitem(mock_rpc_device.status["media"]["playback"], "enable", True)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_rpc_device.mock_update()

    assert len(mock_rpc_device.media_play_or_pause.mock_calls) == 2
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_PLAYING

    monkeypatch.setitem(mock_rpc_device.status["media"]["playback"], "enable", False)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_rpc_device.mock_update()

    mock_rpc_device.media_stop.assert_called_once()
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_IDLE


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
            ATTR_MEDIA_CONTENT_TYPE: CONTENT_TYPE_LOCAL_AUDIO,
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
            ATTR_MEDIA_CONTENT_TYPE: CONTENT_TYPE_LOCAL_RADIO,
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
                ATTR_MEDIA_CONTENT_TYPE: CONTENT_TYPE_LOCAL_RADIO,
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
