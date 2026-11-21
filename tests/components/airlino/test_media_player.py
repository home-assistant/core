"""Tests for the AirLino media player."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

from airlino_api import (
    PLAYER_STATE_PAUSED,
    PLAYER_STATE_PLAYING,
    PLAYER_STATE_STOPPED,
    VOLUME_MAX,
    AirlinoApiConnectionError,
    AirlinoApiError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.components.media_source import PlayMedia
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import MAC

ENTITY_ID = "media_player.living_room"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the media player platform."""
    with patch("homeassistant.components.airlino._PLATFORMS", [Platform.MEDIA_PLAYER]):
        yield


@pytest.mark.freeze_time("2026-01-01 12:00:00+00:00")
@pytest.mark.usefixtures("mock_airlino_api")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the media player entity and its state."""
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_airlino_api")
async def test_device(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the device registry entry."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC), mock_config_entry.entry_id
    )
    assert device == snapshot


async def test_device_name_falls_back_to_entry_title(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_airlino_api: MagicMock,
) -> None:
    """Test the entry title is used when the device reports no name."""
    mock_airlino_api.async_get_device_info.return_value = {"model": "AirLino"}

    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Living room"


@pytest.mark.parametrize(
    ("player_state", "expected_state"),
    [
        pytest.param(PLAYER_STATE_STOPPED, STATE_IDLE, id="stopped"),
        pytest.param(PLAYER_STATE_PLAYING, STATE_PLAYING, id="playing"),
        pytest.param(PLAYER_STATE_PAUSED, STATE_PAUSED, id="paused"),
    ],
)
async def test_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airlino_api: MagicMock,
    player_state: int,
    expected_state: str,
) -> None:
    """Test the player state is mapped to a media player state."""
    mock_airlino_api.async_get_player_status.return_value = {"state": player_state}

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == expected_state


@pytest.mark.parametrize(
    ("status", "attribute", "expected"),
    [
        pytest.param(
            {"station": {"name": "Station", "meta": {"now_playing": "Now playing"}}},
            ATTR_MEDIA_TITLE,
            "Now playing",
            id="title_now_playing",
        ),
        pytest.param(
            {"station": {"name": "Station"}},
            ATTR_MEDIA_TITLE,
            "Station",
            id="title_station",
        ),
        pytest.param(
            {"track": {"meta": {"title": "Song"}}},
            ATTR_MEDIA_TITLE,
            "Song",
            id="title_without_artist",
        ),
        pytest.param({}, ATTR_MEDIA_TITLE, None, id="title_missing"),
        pytest.param(
            {"source": "radio"},
            ATTR_MEDIA_CONTENT_TYPE,
            MediaType.CHANNEL,
            id="content_type_radio",
        ),
        pytest.param(
            {"source": "unknown"},
            ATTR_MEDIA_CONTENT_TYPE,
            None,
            id="content_type_unknown",
        ),
    ],
)
async def test_media_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airlino_api: MagicMock,
    status: dict[str, Any],
    attribute: str,
    expected: str | None,
) -> None:
    """Test media metadata is derived from the player status."""
    mock_airlino_api.async_get_player_status.return_value = {
        "state": PLAYER_STATE_PLAYING,
        "status": status,
    }

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).attributes.get(attribute) == expected


@pytest.mark.parametrize(
    ("player_state", "service", "service_data", "method", "args"),
    [
        pytest.param(
            PLAYER_STATE_STOPPED, SERVICE_MEDIA_PLAY, {}, "async_play", (), id="play"
        ),
        pytest.param(
            PLAYER_STATE_PLAYING,
            SERVICE_MEDIA_PAUSE,
            {},
            "async_playpause",
            (),
            id="pause",
        ),
        pytest.param(
            PLAYER_STATE_PLAYING,
            SERVICE_MEDIA_PLAY_PAUSE,
            {},
            "async_playpause",
            (),
            id="play_pause",
        ),
        pytest.param(
            PLAYER_STATE_PLAYING, SERVICE_MEDIA_STOP, {}, "async_stop", (), id="stop"
        ),
        pytest.param(
            PLAYER_STATE_PLAYING,
            SERVICE_MEDIA_NEXT_TRACK,
            {},
            "async_next",
            (),
            id="next_track",
        ),
        pytest.param(
            PLAYER_STATE_PLAYING,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {},
            "async_previous",
            (),
            id="previous_track",
        ),
        pytest.param(
            PLAYER_STATE_PLAYING,
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
            "async_set_master_volume",
            (round(VOLUME_MAX * 0.5),),
            id="volume_set",
        ),
        pytest.param(
            PLAYER_STATE_PLAYING,
            SERVICE_VOLUME_UP,
            {},
            "async_volume_up",
            (),
            id="volume_up",
        ),
        pytest.param(
            PLAYER_STATE_PLAYING,
            SERVICE_VOLUME_DOWN,
            {},
            "async_volume_down",
            (),
            id="volume_down",
        ),
    ],
)
async def test_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airlino_api: MagicMock,
    player_state: int,
    service: str,
    service_data: dict[str, Any],
    method: str,
    args: tuple[Any, ...],
) -> None:
    """Test media player services call the API and refresh the state."""
    mock_airlino_api.async_get_player_status.return_value = {"state": player_state}
    await setup_integration(hass, mock_config_entry)
    mock_airlino_api.async_get_master_volume.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    getattr(mock_airlino_api, method).assert_awaited_once_with(*args)
    # The volume is only fetched by the coordinator refresh.
    mock_airlino_api.async_get_master_volume.assert_awaited_once()


@pytest.mark.parametrize(
    ("player_state", "service", "method"),
    [
        pytest.param(PLAYER_STATE_PLAYING, SERVICE_MEDIA_PLAY, "async_play", id="play"),
        pytest.param(
            PLAYER_STATE_PAUSED, SERVICE_MEDIA_PAUSE, "async_playpause", id="pause"
        ),
    ],
)
async def test_play_pause_skipped_in_requested_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airlino_api: MagicMock,
    player_state: int,
    service: str,
    method: str,
) -> None:
    """Test play and pause are not sent when the player is already in that state."""
    mock_airlino_api.async_get_player_status.return_value = {"state": player_state}
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    getattr(mock_airlino_api, method).assert_not_awaited()


@pytest.mark.parametrize(
    ("cached_state", "device_state", "service", "method"),
    [
        pytest.param(
            PLAYER_STATE_PLAYING,
            PLAYER_STATE_STOPPED,
            SERVICE_MEDIA_PLAY,
            "async_play",
            id="play",
        ),
        pytest.param(
            PLAYER_STATE_PAUSED,
            PLAYER_STATE_PLAYING,
            SERVICE_MEDIA_PAUSE,
            "async_playpause",
            id="pause",
        ),
    ],
)
async def test_play_pause_use_current_device_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airlino_api: MagicMock,
    cached_state: int,
    device_state: int,
    service: str,
    method: str,
) -> None:
    """Test play and pause are decided on the device state, not the cached one."""
    mock_airlino_api.async_get_player_status.return_value = {"state": cached_state}
    await setup_integration(hass, mock_config_entry)
    mock_airlino_api.async_get_player_status.return_value = {"state": device_state}

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    getattr(mock_airlino_api, method).assert_awaited_once_with()


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        pytest.param(
            AirlinoApiConnectionError("offline"), "cannot_connect", id="offline"
        ),
        pytest.param(AirlinoApiError("failed"), "api_error", id="api_error"),
    ],
)
async def test_service_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airlino_api: MagicMock,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test API failures are raised as translated errors."""
    await setup_integration(hass, mock_config_entry)
    mock_airlino_api.async_stop.side_effect = exception

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_STOP,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key


@pytest.mark.parametrize(
    ("media_type", "media_id", "url"),
    [
        pytest.param(
            MediaType.URL,
            "http://example.test/stream.mp3",
            "http://example.test/stream.mp3",
            id="url",
        ),
        pytest.param(
            MediaType.MUSIC,
            "http://example.test/stream.mp3",
            "http://example.test/stream.mp3",
            id="music",
        ),
        pytest.param(
            "audio/mpeg",
            "http://example.test/stream.mp3",
            "http://example.test/stream.mp3",
            id="audio_mime_type",
        ),
        pytest.param(
            MediaType.URL,
            "https://example.test/stream.mp3",
            "https://example.test/stream.mp3",
            id="https_url",
        ),
        pytest.param(
            MediaType.URL,
            "/local/stream.mp3",
            "http://homeassistant.local:8123/local/stream.mp3",
            id="home_assistant_path",
        ),
    ],
)
async def test_play_media_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airlino_api: MagicMock,
    media_type: str,
    media_id: str,
    url: str,
) -> None:
    """Test playing a stream URL."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://homeassistant.local:8123"}
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: media_id,
        },
        blocking=True,
    )

    mock_airlino_api.async_play_station.assert_awaited_once_with(url)


async def test_play_media_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airlino_api: MagicMock,
) -> None:
    """Test media sources are resolved to an absolute URL."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://homeassistant.local:8123"}
    )
    await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.airlino.media_player.media_source.async_resolve_media",
        return_value=PlayMedia(url="/local/song.mp3", mime_type="audio/mpeg"),
    ) as resolve_media:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: "music",
                ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/song.mp3",
            },
            blocking=True,
        )

    resolve_media.assert_awaited_once_with(
        hass, "media-source://media_source/local/song.mp3", ENTITY_ID
    )
    mock_airlino_api.async_play_station.assert_awaited_once_with(
        "http://homeassistant.local:8123/local/song.mp3"
    )


@pytest.mark.parametrize(
    ("media_type", "media_id", "translation_key"),
    [
        pytest.param(
            MediaType.VIDEO,
            "http://example.test/video.mp4",
            "media_type_unsupported",
            id="unsupported_media_type",
        ),
        pytest.param(
            MediaType.MUSIC,
            "track-id",
            "media_url_invalid",
            id="invalid_url",
        ),
        pytest.param(
            MediaType.URL,
            "http:///stream.mp3",
            "media_url_invalid",
            id="url_without_host",
        ),
    ],
)
async def test_play_media_rejected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airlino_api: MagicMock,
    media_type: str,
    media_id: str,
    translation_key: str,
) -> None:
    """Test media the device cannot play is rejected."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: media_type,
                ATTR_MEDIA_CONTENT_ID: media_id,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    mock_airlino_api.async_play_station.assert_not_awaited()


@pytest.mark.usefixtures("mock_airlino_api")
async def test_browse_media_only_shows_audio(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browsing is limited to audio media."""
    await setup_integration(hass, mock_config_entry)
    root = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="media-source://media_source",
        media_content_type="",
        title="Media",
        can_play=False,
        can_expand=True,
    )
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.airlino.media_player.media_source.async_browse_media",
        return_value=root,
    ) as browse_media:
        await client.send_json_auto_id(
            {"type": "media_player/browse_media", "entity_id": ENTITY_ID}
        )
        response = await client.receive_json()

    assert response["success"]
    content_filter = browse_media.call_args.kwargs["content_filter"]
    assert content_filter(MagicMock(media_content_type="audio/mpeg"))
    assert not content_filter(MagicMock(media_content_type="video/mp4"))
