"""Tests for the AirLino media player."""

from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from airlino_api import (
    PLAYER_STATE_PAUSED,
    PLAYER_STATE_PLAYING,
    VOLUME_MAX,
    AirlinoApiConnectionError,
    AirlinoApiError,
)
import pytest

from homeassistant.components.airlino.const import CONF_SETUP_VERIFIED, DOMAIN
from homeassistant.components.airlino.coordinator import AirlinoDataUpdateCoordinator
from homeassistant.components.airlino.media_player import (
    AirlinoMediaPlayer,
    async_setup_entry as async_setup_media_player_entry,
)
from homeassistant.components.media_player import MediaPlayerState, MediaType
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

PlayerFactory = Callable[
    ..., tuple[AirlinoMediaPlayer, MockConfigEntry, MagicMock, MagicMock]
]


@pytest.fixture
def make_player(hass: HomeAssistant) -> PlayerFactory:
    """Create an AirLino media player with mocked coordinator and API."""

    def create(
        data: dict | None = None,
    ) -> tuple[
        AirlinoMediaPlayer,
        MockConfigEntry,
        MagicMock,
        MagicMock,
    ]:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Living room",
            data={"host": "192.0.2.1"},
            unique_id="00:11:22:33:44:55",
        )
        api = MagicMock()
        for method in (
            "async_play_station",
            "async_play",
            "async_playpause",
            "async_stop",
            "async_next",
            "async_previous",
            "async_set_master_volume",
            "async_volume_up",
            "async_volume_down",
        ):
            setattr(api, method, AsyncMock())
        coordinator = MagicMock(spec=AirlinoDataUpdateCoordinator)
        coordinator.hass = hass
        coordinator.config_entry = entry
        coordinator.api = api
        coordinator.data = {
            "online": True,
            "device": {"devicename": "Living room", "model": "AirLino"},
            "player": {"state": "stopped", "status": {}},
            "volume": 50,
            **(data or {}),
        }
        coordinator.async_request_refresh = AsyncMock()
        entry.runtime_data = coordinator
        player = AirlinoMediaPlayer(coordinator, entry)
        player.hass = hass
        player.entity_id = "media_player.living_room"
        return player, entry, coordinator, api

    return create


async def test_setup_entry_adds_media_player(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Forward entry setup to the media-player platform."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={"host": "192.0.2.1", CONF_SETUP_VERIFIED: True},
        unique_id="00:11:22:33:44:55",
    )
    entry.add_to_hass(hass)
    mock_api = MagicMock()
    mock_api.async_get_device_info = AsyncMock(
        return_value={"devicename": "Living room", "model": "AirLino"}
    )
    mock_api.async_get_player_status = AsyncMock(return_value={"state": "stopped"})
    mock_api.async_get_master_volume = AsyncMock(return_value=50)
    platform_setup = AsyncMock(wraps=async_setup_media_player_entry)

    with (
        patch("homeassistant.components.airlino.AirlinoApi", return_value=mock_api),
        patch(
            "homeassistant.components.airlino.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.airlino.media_player.async_setup_entry",
            new=platform_setup,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    platform_setup.assert_awaited_once()
    assert (
        entity_registry.async_get_entity_id("media_player", DOMAIN, entry.unique_id)
        is not None
    )


async def test_availability_requires_online_and_coordinator_available(
    make_player: PlayerFactory,
) -> None:
    """Require both the device and coordinator to report availability."""
    player, _, coordinator, _ = make_player({"online": False})
    coordinator.last_update_success = True
    assert player.available is False

    coordinator.data["online"] = True
    coordinator.last_update_success = False
    assert player.available is False


async def test_missing_volume_returns_none(make_player: PlayerFactory) -> None:
    """Return no volume when the coordinator has not reported it."""
    player, _, _, _ = make_player({"volume": None})

    assert player.volume_level is None


async def test_state_volume_and_metadata(make_player: PlayerFactory) -> None:
    """Expose playback state, volume, and track metadata from coordinator data."""
    player, _, _, _ = make_player(
        {
            "player": {
                "state": PLAYER_STATE_PLAYING,
                "status": {
                    "source": "tidal",
                    "elapsedtime": 12,
                    "track": {
                        "meta": {"artist": "Artist", "title": "Song"},
                        "totaltime": 180,
                        "image": "http://example.test/cover.jpg",
                    },
                },
            },
            "volume": 25,
        }
    )

    assert player.state is MediaPlayerState.PLAYING
    assert player.volume_level == 25 / VOLUME_MAX
    assert player.media_title == "Artist - Song"
    assert player.media_duration == 180
    assert player.media_position == 12
    assert player.media_image_url == "http://example.test/cover.jpg"


@pytest.mark.parametrize(
    ("data", "expected_state"),
    [
        ({"player": {"state": PLAYER_STATE_PAUSED}}, MediaPlayerState.PAUSED),
        ({"player": {"state": "unknown"}}, None),
        ({"player": {}}, None),
    ],
)
async def test_state_uses_player_status(
    data: dict, expected_state: MediaPlayerState | None, make_player: PlayerFactory
) -> None:
    """Map player API states to Home Assistant states."""
    player, _, _, _ = make_player(data)

    assert player.state is expected_state


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("radio", MediaType.CHANNEL),
        ("tidal", MediaType.MUSIC),
        ("qobuz", MediaType.MUSIC),
        ("other", MediaType.MUSIC),
        ("unknown", None),
        (None, None),
        (1, None),
    ],
)
async def test_media_content_type(
    source: str | int | None,
    expected: MediaType | None,
    make_player: PlayerFactory,
) -> None:
    """Map recognized playback sources to Home Assistant media types."""
    player, _, _, _ = make_player({"player": {"status": {"source": source}}})

    assert player.media_content_type == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ({"station": {"meta": {"now_playing": "Now playing"}}}, "Now playing"),
        ({"station": {"name": "Station"}}, "Station"),
        ({"track": {"meta": {"title": "Song"}}}, "Song"),
        (
            {"track": {"meta": {"artist": "Artist", "title": "Song"}}},
            "Artist - Song",
        ),
        ({}, None),
    ],
)
async def test_media_title_fallbacks(
    status: dict, expected: str | None, make_player: PlayerFactory
) -> None:
    """Choose the best available station or track title."""
    player, _, _, _ = make_player({"player": {"status": status}})

    assert player.media_title == expected


async def test_device_info_uses_entry_title_when_name_missing(
    make_player: PlayerFactory,
) -> None:
    """Fall back to the configured title when device info lacks a name."""
    player, _, _, _ = make_player({"device": {"model": "AirLino"}})

    device_info = player.device_info
    assert device_info["name"] == "Living room"
    assert device_info["model"] == "AirLino"


async def test_media_position_updated_at_only_accepts_datetime(
    make_player: PlayerFactory,
) -> None:
    """Expose the update timestamp only when it is a datetime."""
    player, _, coordinator, _ = make_player()
    timestamp = dt_util.utcnow()
    coordinator.data["updated_at"] = timestamp

    assert player.media_position_updated_at == timestamp

    coordinator.data["updated_at"] = "invalid"
    assert player.media_position_updated_at is None


async def test_play_media_resolves_media_source_and_normalizes_url(
    make_player: PlayerFactory,
) -> None:
    """Resolve media-source content and normalize the URL before playback."""
    player, _, _, api = make_player()
    resolved = SimpleNamespace(url="/api/media_source_proxy/audio")
    with (
        patch(
            "homeassistant.components.airlino.media_player.is_media_source_id",
            return_value=True,
        ),
        patch(
            "homeassistant.components.airlino.media_player.media_source.async_resolve_media",
            return_value=resolved,
        ) as resolve_media,
        patch(
            "homeassistant.components.airlino.media_player.async_process_play_media_url",
            return_value="http://ha.local/api/media_source_proxy/audio?auth=token",
        ) as process_url,
    ):
        await player.async_play_media("music", "media-source://media_source/item")

    resolve_media.assert_awaited_once_with(
        player.hass, "media-source://media_source/item", player.entity_id
    )
    process_url.assert_called_once_with(player.hass, resolved.url)
    api.async_play_station.assert_awaited_once_with(
        "http://ha.local/api/media_source_proxy/audio?auth=token"
    )


async def test_browse_media_filters_to_audio(
    make_player: PlayerFactory,
) -> None:
    """Delegate media browsing with an audio-only filter."""
    player, _, _, _ = make_player()
    browse_result = MagicMock()
    with patch(
        "homeassistant.components.airlino.media_player.media_source.async_browse_media",
        new_callable=AsyncMock,
        return_value=browse_result,
    ) as browse_media:
        result = await player.async_browse_media("music", "media-source://root")

    assert result is browse_result
    browse_media.assert_awaited_once()
    content_filter = browse_media.call_args.kwargs["content_filter"]
    audio_item = MagicMock()
    audio_item.media_content_type = "audio/mpeg"
    video_item = MagicMock()
    video_item.media_content_type = "video/mp4"
    assert content_filter(audio_item) is True
    assert content_filter(video_item) is False


async def test_direct_url_is_normalized_before_playback(
    make_player: PlayerFactory,
) -> None:
    """Normalize Home Assistant-relative URLs before sending them to AirLino."""
    player, _, _, api = make_player()
    with patch(
        "homeassistant.components.airlino.media_player.async_process_play_media_url",
        return_value="http://ha.local/local/stream?auth=token",
    ) as process_url:
        await player.async_play_media("url", "/local/stream")

    process_url.assert_called_once_with(player.hass, "/local/stream")
    api.async_play_station.assert_awaited_once_with(
        "http://ha.local/local/stream?auth=token"
    )


async def test_play_media_rejects_unsupported_types(make_player: PlayerFactory) -> None:
    """Reject non-URL media types without calling the device API."""
    player, _, _, api = make_player()

    with pytest.raises(ServiceValidationError):
        await player.async_play_media("music", "track-id")
    api.async_play_station.assert_not_awaited()


async def test_play_media_rejects_https(make_player: PlayerFactory) -> None:
    """Reject HTTPS URLs that the device cannot play."""
    player, _, _, api = make_player()

    with pytest.raises(HomeAssistantError):
        await player.async_play_media("url", "https://example.test/stream")
    api.async_play_station.assert_not_awaited()


async def test_repeated_play_media_errors_each_raise(
    make_player: PlayerFactory,
) -> None:
    """Raise for each failed stream command, including repeated errors."""
    player, _, _, api = make_player()
    api.async_play_station.side_effect = AirlinoApiError("invalid stream")

    for _ in range(2):
        with pytest.raises(HomeAssistantError):
            await player.async_play_media("url", "http://example.test/stream")

    assert api.async_play_station.await_count == 2


async def test_play_pause_stop_track_and_volume_commands_refresh(
    make_player: PlayerFactory,
) -> None:
    """Refresh entity data after each successful playback and volume command."""
    player, _, coordinator, api = make_player(
        {"player": {"state": PLAYER_STATE_PLAYING, "status": {}}}
    )

    await player.async_media_pause()
    await player.async_media_play_pause()
    await player.async_media_stop()
    await player.async_media_next_track()
    await player.async_media_previous_track()
    await player.async_volume_down()

    assert api.async_playpause.await_count == 2
    api.async_stop.assert_awaited_once()
    api.async_next.assert_awaited_once()
    api.async_previous.assert_awaited_once()
    api.async_volume_down.assert_awaited_once()
    assert coordinator.async_request_refresh.await_count == 6


async def test_play_and_pause_are_noops_when_already_in_requested_state(
    make_player: PlayerFactory,
) -> None:
    """Skip redundant play and pause commands."""
    player, _, coordinator, api = make_player(
        {"player": {"state": PLAYER_STATE_PLAYING}}
    )

    await player.async_media_play()
    api.async_play.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_awaited()

    player.coordinator.data["player"]["state"] = PLAYER_STATE_PAUSED
    await player.async_media_pause()
    api.async_playpause.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_awaited()


async def test_play_and_volume_commands_refresh_coordinator(
    make_player: PlayerFactory,
) -> None:
    """Refresh coordinator data after play and volume commands."""
    player, _, coordinator, api = make_player()

    await player.async_media_play()
    api.async_play.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited_once()

    coordinator.async_request_refresh.reset_mock()
    await player.async_set_volume_level(0.5)
    api.async_set_master_volume.assert_awaited_once_with(round(VOLUME_MAX * 0.5))
    coordinator.async_request_refresh.assert_awaited_once()

    coordinator.async_request_refresh.reset_mock()
    await player.async_volume_up()
    api.async_volume_up.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited_once()


async def test_play_media_command_error_becomes_home_assistant_error(
    make_player: PlayerFactory,
) -> None:
    """Translate failed stream-play commands and skip refresh on failure."""
    player, _, coordinator, api = make_player()
    api.async_play_station.side_effect = AirlinoApiError("invalid stream")

    with pytest.raises(HomeAssistantError):
        await player.async_play_media("url", "http://example.test/stream")

    coordinator.async_request_refresh.assert_not_awaited()


async def test_api_command_error_becomes_home_assistant_error(
    make_player: PlayerFactory,
) -> None:
    """Convert AirLino API command failures to Home Assistant errors."""
    player, _, _, api = make_player()
    api.async_play.side_effect = AirlinoApiConnectionError("request failed")

    with pytest.raises(HomeAssistantError):
        await player.async_media_play()
