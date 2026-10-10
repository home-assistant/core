"""Tests for the AirLino media player."""

from unittest.mock import AsyncMock, MagicMock

from airlino_api import PLAYER_STATE_PLAYING, VOLUME_MAX, AirlinoApiConnectionError
import pytest

from homeassistant.components.airlino import AirlinoRuntimeData
from homeassistant.components.airlino.const import DOMAIN
from homeassistant.components.airlino.coordinator import AirlinoDataUpdateCoordinator
from homeassistant.components.airlino.media_player import AirlinoMediaPlayer
from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


@pytest.fixture
def make_player(hass: HomeAssistant):
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
            "async_enable_sender",
            "async_disable_sender",
            "async_receiver_unlink",
            "async_receiver_link",
        ):
            setattr(api, method, AsyncMock())
        api.async_get_sender_status = AsyncMock(
            return_value={"uuid": "sender-uuid", "enabled": False}
        )
        api.async_get_receiver_state = AsyncMock(return_value={"sender": None})
        coordinator = MagicMock(spec=AirlinoDataUpdateCoordinator)
        coordinator.hass = hass
        coordinator.api = api
        coordinator.data = {
            "online": True,
            "device": {"devicename": "Living room", "model": "AirLino"},
            "player": {"state": "stopped", "status": {}},
            "volume": 50,
            "sender": None,
            "receiver": None,
            **(data or {}),
        }
        coordinator.async_request_refresh = AsyncMock()
        player = AirlinoMediaPlayer(coordinator, entry)
        player.hass = hass
        player.entity_id = "media_player.living_room"
        return player, entry, coordinator, api

    return create


async def test_availability_requires_online_and_coordinator_available(
    make_player,
) -> None:
    """Require both the device and coordinator to report availability."""
    player, _, coordinator, _ = make_player({"online": False})
    coordinator.last_update_success = True
    assert player.available is False

    coordinator.data["online"] = True
    coordinator.last_update_success = False
    assert player.available is False


async def test_state_volume_and_metadata(make_player) -> None:
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


async def test_receiver_has_restricted_features_and_cannot_play(make_player) -> None:
    """Restrict direct playback commands on multiroom receivers."""
    player, _, _, api = make_player({"receiver": {"sender": "master-uuid"}})

    assert player.is_multiroom_receiver
    assert player.supported_features == (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.GROUPING
    )
    with pytest.raises(HomeAssistantError):
        await player.async_media_play()
    api.async_play.assert_not_awaited()


async def test_play_media_rejects_unsupported_types(make_player) -> None:
    """Reject non-URL media types without calling the device API."""
    player, _, _, api = make_player()

    with pytest.raises(HomeAssistantError):
        await player.async_play_media("music", "track-id")
    api.async_play_station.assert_not_awaited()


async def test_play_media_rejects_https(make_player) -> None:
    """Reject HTTPS URLs that the device cannot play."""
    player, _, _, api = make_player()

    with pytest.raises(HomeAssistantError):
        await player.async_play_media("url", "https://example.test/stream")
    api.async_play_station.assert_not_awaited()


async def test_play_and_volume_commands_refresh_coordinator(make_player) -> None:
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


async def test_api_command_error_becomes_home_assistant_error(make_player) -> None:
    """Convert AirLino API command failures to Home Assistant errors."""
    player, _, _, api = make_player()
    api.async_play.side_effect = AirlinoApiConnectionError("request failed")

    with pytest.raises(HomeAssistantError):
        await player.async_media_play()


async def test_join_rejects_unknown_member_before_mutations(make_player) -> None:
    """Validate unknown group members before enabling the sender."""
    player, _, _, api = make_player()

    with pytest.raises(HomeAssistantError):
        await player.async_join_players(["media_player.unknown"])

    api.async_enable_sender.assert_not_awaited()
    api.async_receiver_link.assert_not_awaited()


async def test_join_ignores_self_and_links_requested_receiver(make_player) -> None:
    """Skip the command target and link other requested devices."""
    player, _, coordinator, api = make_player()
    receiver_api = MagicMock()
    receiver_api.async_get_receiver_state = AsyncMock(return_value={"sender": None})
    receiver_api.async_receiver_link = AsyncMock()
    receiver_coordinator = MagicMock()
    receiver_coordinator.data = {"online": True}
    receiver_coordinator.async_request_refresh = AsyncMock()
    runtime = AirlinoRuntimeData(api=receiver_api, coordinator=receiver_coordinator)
    player._async_find_runtime_by_entity_id = AsyncMock(return_value=runtime)

    await player.async_join_players([player.entity_id, "media_player.kitchen"])

    api.async_enable_sender.assert_awaited_once()
    receiver_api.async_receiver_link.assert_awaited_once_with("sender-uuid")
    receiver_coordinator.async_request_refresh.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited_once()


async def test_offline_member_fails_before_enabling_sender(make_player) -> None:
    """Reject offline group members before changing sender state."""
    player, _, _, api = make_player()
    offline_api = MagicMock()
    offline_coordinator = MagicMock()
    offline_coordinator.data = {"online": False}
    runtime = AirlinoRuntimeData(api=offline_api, coordinator=offline_coordinator)
    player._async_find_runtime_by_entity_id = AsyncMock(return_value=runtime)

    with pytest.raises(HomeAssistantError):
        await player.async_join_players(["media_player.kitchen"])

    api.async_enable_sender.assert_not_awaited()
    offline_api.async_receiver_link.assert_not_called()
