"""Tests for the AirLino media player."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from airlino_api import (
    PLAYER_STATE_PLAYING,
    RECEIVER_STATE_NOT_PLAYING,
    RECEIVER_STATE_PLAYING,
    SENDER_STATE_PLAYING,
    VOLUME_MAX,
    AirlinoApiConnectionError,
    AirlinoApiError,
)
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
from homeassistant.util import dt as dt_util

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


@pytest.mark.parametrize(
    ("data", "expected_state"),
    [
        ({"receiver": {"state": RECEIVER_STATE_PLAYING}}, MediaPlayerState.PLAYING),
        (
            {"receiver": {"state": RECEIVER_STATE_NOT_PLAYING}},
            MediaPlayerState.PAUSED,
        ),
        (
            {
                "sender": {
                    "enabled": True,
                    "uuid": "sender-uuid",
                    "state": SENDER_STATE_PLAYING,
                }
            },
            MediaPlayerState.PLAYING,
        ),
        ({"sender": {"enabled": True, "uuid": "sender-uuid"}}, MediaPlayerState.IDLE),
    ],
)
async def test_state_uses_songcast_status(
    data: dict, expected_state: MediaPlayerState, make_player
) -> None:
    """Prefer receiver and sender playback status where available."""
    player, _, _, _ = make_player(data)

    assert player.state is expected_state


async def test_device_info_uses_entry_title_when_name_missing(make_player) -> None:
    """Fall back to the configured title when device info lacks a name."""
    player, _, _, _ = make_player({"device": {"model": "AirLino"}})

    device_info = player.device_info
    assert device_info["name"] == "Living room"
    assert device_info["model"] == "AirLino"


async def test_group_members_include_master_and_receivers(make_player) -> None:
    """Return sorted entity IDs for the sender and its linked receivers."""
    player, entry, coordinator, _ = make_player(
        {"sender": {"enabled": True, "uuid": "sender-uuid"}}
    )
    receiver_coordinator = MagicMock()
    receiver_coordinator.data = {"receiver": {"sender": "sender-uuid"}}
    receiver_entry = MagicMock()
    player._all_runtimes = MagicMock(
        return_value=[
            (entry, AirlinoRuntimeData(api=MagicMock(), coordinator=coordinator)),
            (
                receiver_entry,
                AirlinoRuntimeData(api=MagicMock(), coordinator=receiver_coordinator),
            ),
        ]
    )
    player._entity_id_for_entry = MagicMock(
        side_effect=["media_player.living_room", "media_player.kitchen"]
    )

    assert player.group_members == ["media_player.kitchen", "media_player.living_room"]


async def test_group_members_is_none_without_sender(make_player) -> None:
    """Return no group members for a standalone device."""
    player, _, _, _ = make_player()

    assert player.group_members is None


async def test_group_members_without_registered_entity_ids_returns_none(
    make_player,
) -> None:
    """Return no group when none of its members has a registered entity."""
    player, entry, coordinator, _ = make_player(
        {"sender": {"enabled": True, "uuid": "sender-uuid"}}
    )
    player._all_runtimes = MagicMock(
        return_value=[
            (entry, AirlinoRuntimeData(api=MagicMock(), coordinator=coordinator))
        ]
    )
    player._entity_id_for_entry = MagicMock(return_value=None)

    assert player.group_members is None


async def test_async_find_runtime_returns_none_for_unknown_entity(make_player) -> None:
    """Return no runtime when no loaded integration entry matches the entity."""
    player, _, _, _ = make_player()
    player._all_runtimes = MagicMock(return_value=[])

    assert await player._async_find_runtime_by_entity_id("media_player.unknown") is None


async def test_media_position_updated_at_only_accepts_datetime(make_player) -> None:
    """Expose the update timestamp only when it is a datetime."""
    player, _, coordinator, _ = make_player()
    timestamp = dt_util.utcnow()
    coordinator.data["updated_at"] = timestamp

    assert player.media_position_updated_at == timestamp

    coordinator.data["updated_at"] = "invalid"
    assert player.media_position_updated_at is None


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


async def test_play_media_resolves_media_source_and_normalizes_url(make_player) -> None:
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


async def test_direct_url_is_normalized_before_playback(make_player) -> None:
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


async def test_repeated_play_media_errors_each_raise(make_player) -> None:
    """Raise for each failed stream command, including repeated errors."""
    player, _, _, api = make_player()
    api.async_play_station.side_effect = AirlinoApiError("invalid stream")

    for _ in range(2):
        with pytest.raises(HomeAssistantError):
            await player.async_play_media("url", "http://example.test/stream")

    assert api.async_play_station.await_count == 2


async def test_play_pause_stop_track_and_volume_commands_refresh(make_player) -> None:
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


async def test_play_media_command_error_becomes_home_assistant_error(
    make_player,
) -> None:
    """Translate failed stream-play commands and skip refresh on failure."""
    player, _, coordinator, api = make_player()
    api.async_play_station.side_effect = AirlinoApiError("invalid stream")

    with pytest.raises(HomeAssistantError):
        await player.async_play_media("url", "http://example.test/stream")

    coordinator.async_request_refresh.assert_not_awaited()


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


async def test_join_requires_sender_uuid(make_player) -> None:
    """Reject group creation when the sender has no UUID."""
    player, _, _, api = make_player()
    api.async_get_sender_status.return_value = {"enabled": False}

    with pytest.raises(HomeAssistantError):
        await player.async_join_players(["media_player.kitchen"])

    api.async_enable_sender.assert_not_awaited()


async def test_join_does_not_reenable_or_relink_existing_group(make_player) -> None:
    """Avoid re-enabling an active sender or relinking an attached receiver."""
    player, _, coordinator, api = make_player(
        {"sender": {"enabled": True, "uuid": "sender-uuid"}}
    )
    api.async_get_sender_status.return_value = {
        "enabled": True,
        "uuid": "sender-uuid",
    }
    receiver_api = MagicMock()
    receiver_api.async_get_receiver_state = AsyncMock(
        return_value={"sender": "sender-uuid"}
    )
    receiver_api.async_get_sender_status = AsyncMock(return_value={"enabled": False})
    receiver_api.async_receiver_link = AsyncMock()
    receiver_coordinator = MagicMock()
    receiver_coordinator.data = {"online": True}
    receiver_coordinator.async_request_refresh = AsyncMock()
    runtime = AirlinoRuntimeData(api=receiver_api, coordinator=receiver_coordinator)
    player._async_find_runtime_by_entity_id = AsyncMock(return_value=runtime)

    await player.async_join_players(["media_player.kitchen"])

    api.async_enable_sender.assert_not_awaited()
    receiver_api.async_receiver_link.assert_not_awaited()
    receiver_coordinator.async_request_refresh.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited_once()


async def test_join_ignores_self_and_links_requested_receiver(make_player) -> None:
    """Skip the command target and link other requested devices."""
    player, _, coordinator, api = make_player()
    receiver_api = MagicMock()
    receiver_api.async_get_receiver_state = AsyncMock(return_value={"sender": None})
    receiver_api.async_get_sender_status = AsyncMock(return_value={"enabled": False})
    receiver_api.async_receiver_link = AsyncMock()
    receiver_coordinator = MagicMock()
    receiver_coordinator.data = {"online": True}
    receiver_coordinator.async_request_refresh = AsyncMock()
    runtime = AirlinoRuntimeData(api=receiver_api, coordinator=receiver_coordinator)
    player._async_find_runtime_by_entity_id = AsyncMock(return_value=runtime)

    await player.async_join_players([player.entity_id, "media_player.kitchen"])

    api.async_enable_sender.assert_awaited_once_with("Living room Group")
    receiver_api.async_receiver_link.assert_awaited_once_with("sender-uuid")
    receiver_coordinator.async_request_refresh.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited_once()


async def test_empty_or_self_only_join_does_not_enable_sender(make_player) -> None:
    """Do not leave a sender running when no receivers were requested."""
    player, _, coordinator, api = make_player()

    await player.async_join_players([])
    await player.async_join_players([player.entity_id])

    api.async_enable_sender.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_awaited()


async def test_unjoin_sender_does_not_unlink_unrelated_receivers(make_player) -> None:
    """Leave receivers in other groups untouched while disabling this sender."""
    player, _, coordinator, api = make_player(
        {"sender": {"enabled": True, "uuid": "sender-uuid"}}
    )
    unrelated_api = MagicMock()
    unrelated_api.async_receiver_unlink = AsyncMock()
    unrelated_coordinator = MagicMock()
    unrelated_coordinator.data = {"receiver": {"sender": "different-sender"}}
    unrelated_coordinator.async_request_refresh = AsyncMock()
    unrelated_runtime = AirlinoRuntimeData(
        api=unrelated_api, coordinator=unrelated_coordinator
    )
    player._all_runtimes = MagicMock(
        return_value=[
            (None, AirlinoRuntimeData(api=api, coordinator=coordinator)),
            (None, unrelated_runtime),
        ]
    )

    await player.async_unjoin_player()

    unrelated_api.async_receiver_unlink.assert_not_awaited()
    unrelated_coordinator.async_request_refresh.assert_not_awaited()
    api.async_disable_sender.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited_once()


async def test_unjoin_sender_unlinks_receivers_and_disables_sender(make_player) -> None:
    """Dissolve a sender group by unlinking each receiver first."""
    player, _, coordinator, api = make_player(
        {"sender": {"enabled": True, "uuid": "sender-uuid"}}
    )
    receiver_api = MagicMock()
    receiver_api.async_receiver_unlink = AsyncMock()
    receiver_coordinator = MagicMock()
    receiver_coordinator.data = {"receiver": {"sender": "sender-uuid"}}
    receiver_coordinator.async_request_refresh = AsyncMock()
    receiver_runtime = AirlinoRuntimeData(
        api=receiver_api, coordinator=receiver_coordinator
    )
    player._all_runtimes = MagicMock(
        return_value=[
            (None, AirlinoRuntimeData(api=api, coordinator=coordinator)),
            (None, receiver_runtime),
        ]
    )

    await player.async_unjoin_player()

    receiver_api.async_receiver_unlink.assert_awaited_once()
    receiver_coordinator.async_request_refresh.assert_awaited_once()
    api.async_disable_sender.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited_once()


async def test_unjoin_receiver_only_unlinks_requested_receiver(make_player) -> None:
    """Unlink only the requested receiver without inspecting cached members."""
    player, _, coordinator, api = make_player({"receiver": {"sender": "master-uuid"}})

    await player.async_unjoin_player()

    api.async_receiver_unlink.assert_awaited_once()
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


@pytest.mark.parametrize(
    ("receiver_state", "sender_state"),
    [
        ({"sender": "another-master"}, {"enabled": False}),
        ({"sender": None}, {"enabled": True, "uuid": "member-sender"}),
    ],
)
async def test_join_rejects_member_already_in_group(
    make_player, receiver_state: dict, sender_state: dict
) -> None:
    """Reject grouped receivers and active senders before changing groups."""
    player, _, _, sender_api = make_player()
    member_api = MagicMock()
    member_api.async_get_receiver_state = AsyncMock(return_value=receiver_state)
    member_api.async_get_sender_status = AsyncMock(return_value=sender_state)
    member_api.async_receiver_unlink = AsyncMock()
    member_api.async_receiver_link = AsyncMock()
    member_coordinator = MagicMock()
    member_coordinator.data = {"online": True}
    runtime = AirlinoRuntimeData(api=member_api, coordinator=member_coordinator)
    player._async_find_runtime_by_entity_id = AsyncMock(return_value=runtime)

    with pytest.raises(HomeAssistantError):
        await player.async_join_players(["media_player.kitchen"])

    sender_api.async_enable_sender.assert_not_awaited()
    member_api.async_receiver_unlink.assert_not_awaited()
    member_api.async_receiver_link.assert_not_awaited()
