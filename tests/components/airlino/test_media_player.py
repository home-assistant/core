"""Tests for the AirLino media player."""

import asyncio
from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from airlino_api import (
    PLAYER_STATE_PAUSED,
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
from homeassistant.components.airlino.const import CONF_SETUP_VERIFIED, DOMAIN
from homeassistant.components.airlino.coordinator import AirlinoDataUpdateCoordinator
from homeassistant.components.airlino.media_player import (
    AirlinoMediaPlayer,
    async_setup_entry as async_setup_media_player_entry,
)
from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntryState
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
        coordinator.config_entry = entry
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
        entry.runtime_data = AirlinoRuntimeData(api=api, coordinator=coordinator)
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
    mock_api.async_get_sender_status = AsyncMock(return_value={"enabled": False})
    mock_api.async_get_receiver_state = AsyncMock(return_value={"sender": None})
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
    """Map player API states to Home Assistant states when not grouped."""
    player, _, _, _ = make_player(data)

    assert player.state is expected_state


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
    data: dict, expected_state: MediaPlayerState, make_player: PlayerFactory
) -> None:
    """Prefer receiver and sender playback status where available."""
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


async def _setup_group_devices(
    hass: HomeAssistant,
    devices: list[tuple[str, str, bool, str | None]],
) -> list[MockConfigEntry]:
    apis: list[MagicMock] = []
    entries: list[MockConfigEntry] = []
    for index, (title, mac, sender_enabled, receiver_sender) in enumerate(devices):
        host = f"192.0.2.{index + 1}"
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=title,
            data={"host": host, CONF_SETUP_VERIFIED: True},
            unique_id=mac,
        )
        entry.add_to_hass(hass)
        api = MagicMock()
        api.async_enable_sender = AsyncMock()
        api.async_disable_sender = AsyncMock()
        api.async_receiver_link = AsyncMock()
        api.async_receiver_unlink = AsyncMock()
        api.async_get_device_info = AsyncMock(
            return_value={"devicename": title, "model": "AirLino"}
        )
        api.async_get_player_status = AsyncMock(return_value={"state": "stopped"})
        api.async_get_master_volume = AsyncMock(return_value=50)
        api.async_get_sender_status = AsyncMock(
            return_value={
                "enabled": sender_enabled,
                "uuid": f"sender-{title}",
            }
        )
        api.async_get_receiver_state = AsyncMock(
            return_value={"sender": receiver_sender}
        )
        apis.append(api)
        entries.append(entry)

    with (
        patch(
            "homeassistant.components.airlino.AirlinoApi",
            side_effect=apis,
        ),
        patch(
            "homeassistant.components.airlino.async_get_clientsession",
            return_value=MagicMock(),
        ),
    ):
        assert await hass.config_entries.async_setup(entries[0].entry_id)

    assert all(entry.state is ConfigEntryState.LOADED for entry in entries)
    return entries


async def test_group_members_include_master_and_receivers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Return sorted entity IDs for the loaded master and receiver entries."""
    master, receiver = await _setup_group_devices(
        hass,
        [
            ("Living room", "00:11:22:33:44:55", True, None),
            ("Kitchen", "00:11:22:33:44:66", False, "sender-Living room"),
        ],
    )
    player = AirlinoMediaPlayer(master.runtime_data.coordinator, master)
    player.hass = hass
    player._group_mutation_lock = master.runtime_data.group_mutation_lock
    player.entity_id = entity_registry.async_get_entity_id(
        "media_player", DOMAIN, master.unique_id
    )

    assert player.group_members == [
        "media_player.kitchen",
        "media_player.living_room",
    ]
    assert (
        entity_registry.async_get_entity_id("media_player", DOMAIN, master.unique_id)
        == "media_player.living_room"
    )
    assert (
        entity_registry.async_get_entity_id("media_player", DOMAIN, receiver.unique_id)
        == "media_player.kitchen"
    )


async def test_group_members_skips_unrelated_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Ignore loaded entries that are not part of the sender's group."""
    master, _receiver, unrelated = await _setup_group_devices(
        hass,
        [
            ("Living room", "00:11:22:33:44:55", True, None),
            ("Kitchen", "00:11:22:33:44:66", False, "sender-Living room"),
            ("Bedroom", "00:11:22:33:44:77", True, None),
        ],
    )
    player = AirlinoMediaPlayer(master.runtime_data.coordinator, master)
    player.hass = hass
    player._group_mutation_lock = master.runtime_data.group_mutation_lock
    player.entity_id = entity_registry.async_get_entity_id(
        "media_player", DOMAIN, master.unique_id
    )

    group_members = player.group_members

    assert group_members == [
        "media_player.kitchen",
        "media_player.living_room",
    ]
    assert (
        entity_registry.async_get_entity_id("media_player", DOMAIN, unrelated.unique_id)
        == "media_player.bedroom"
    )
    assert "media_player.bedroom" not in group_members


async def test_group_members_is_none_without_sender(make_player: PlayerFactory) -> None:
    """Return no group members for a standalone device."""
    player, _, _, _ = make_player()

    assert player.group_members is None


async def test_group_members_without_registered_entity_ids_returns_none(
    make_player: PlayerFactory,
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


async def test_entity_id_for_entry_returns_registry_entity(
    hass: HomeAssistant, make_player: PlayerFactory
) -> None:
    """Look up registered AirLino media-player entities."""
    player, entry, _, _ = make_player()
    entity_registry = MagicMock()
    entity_registry.async_get_entity_id.return_value = "media_player.living_room"
    with patch(
        "homeassistant.components.airlino.media_player.er.async_get",
        return_value=entity_registry,
    ):
        entity_id = player._entity_id_for_entry(entry)

    assert entity_id == "media_player.living_room"
    entity_registry.async_get_entity_id.assert_called_once_with(
        "media_player", DOMAIN, entry.unique_id
    )


async def test_async_find_runtime_returns_matching_runtime(
    make_player: PlayerFactory,
) -> None:
    """Return runtime data for a registered entity ID."""
    player, entry, coordinator, api = make_player()
    runtime = AirlinoRuntimeData(api=api, coordinator=coordinator)
    player._all_runtimes = MagicMock(return_value=[(entry, runtime)])
    player._entity_id_for_entry = MagicMock(return_value="media_player.living_room")

    assert (
        await player._async_find_runtime_by_entity_id("media_player.living_room")
        is runtime
    )


async def test_async_find_runtime_returns_none_for_unknown_entity(
    make_player: PlayerFactory,
) -> None:
    """Return no runtime when no loaded integration entry matches the entity."""
    player, _, _, _ = make_player()
    player._all_runtimes = MagicMock(return_value=[])

    assert await player._async_find_runtime_by_entity_id("media_player.unknown") is None


async def test_empty_songcast_status_uses_empty_mappings(
    make_player: PlayerFactory,
) -> None:
    """Handle absent playback, sender, and receiver payloads."""
    player, _, _, _ = make_player({"player": {}, "sender": None, "receiver": None})

    assert player.state is None
    assert player.is_multiroom_receiver is False
    assert player.group_members is None


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


async def test_non_receiver_has_full_features(make_player: PlayerFactory) -> None:
    """Expose all controls when the device is not a Songcast receiver."""
    player, _, _, _ = make_player()

    assert player.supported_features == player._attr_supported_features


async def test_receiver_has_restricted_features_and_cannot_play(
    make_player: PlayerFactory,
) -> None:
    """Restrict direct playback commands on multiroom receivers."""
    player, _, _, api = make_player({"receiver": {"sender": "master-uuid"}})

    assert player.is_multiroom_receiver
    assert player.supported_features == (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.GROUPING
    )
    with pytest.raises(ServiceValidationError):
        await player.async_media_play()
    api.async_play.assert_not_awaited()


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


async def test_join_rejects_unknown_member_before_mutations(
    make_player: PlayerFactory,
) -> None:
    """Validate unknown group members before enabling the sender."""
    player, _, _, api = make_player()

    with pytest.raises(ServiceValidationError):
        await player.async_join_players(["media_player.unknown"])

    api.async_enable_sender.assert_not_awaited()
    api.async_receiver_link.assert_not_awaited()


async def test_join_requires_sender_uuid(make_player: PlayerFactory) -> None:
    """Reject group creation when the sender has no UUID."""
    player, _, _, api = make_player()
    api.async_get_sender_status.return_value = {"enabled": False}

    with pytest.raises(ServiceValidationError):
        await player.async_join_players(["media_player.kitchen"])

    api.async_enable_sender.assert_not_awaited()


async def test_join_does_not_reenable_or_relink_existing_group(
    make_player: PlayerFactory,
) -> None:
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


async def test_join_deduplicates_requested_receivers(
    make_player: PlayerFactory,
) -> None:
    """Validate and link a repeated receiver only once."""
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

    await player.async_join_players(["media_player.kitchen", "media_player.kitchen"])

    player._async_find_runtime_by_entity_id.assert_awaited_once_with(
        "media_player.kitchen"
    )
    receiver_api.async_get_receiver_state.assert_awaited_once()
    receiver_api.async_get_sender_status.assert_awaited_once()
    receiver_api.async_receiver_link.assert_awaited_once_with("sender-uuid")
    receiver_coordinator.async_request_refresh.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited_once()
    api.async_enable_sender.assert_awaited_once_with("Living room Group")


async def test_join_ignores_self_and_links_requested_receiver(
    make_player: PlayerFactory,
) -> None:
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


async def test_overlapping_joins_serialize_receiver_mutations(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Prevent two masters from concurrently claiming one receiver."""
    first_entry, second_entry, receiver_entry = await _setup_group_devices(
        hass,
        [
            ("Living room", "00:11:22:33:44:55", False, None),
            ("Office", "00:11:22:33:44:66", False, None),
            ("Kitchen", "00:11:22:33:44:77", False, None),
        ],
    )
    first_player = AirlinoMediaPlayer(first_entry.runtime_data.coordinator, first_entry)
    second_player = AirlinoMediaPlayer(
        second_entry.runtime_data.coordinator, second_entry
    )
    for player, entry in ((first_player, first_entry), (second_player, second_entry)):
        player.hass = hass
        player.entity_id = entity_registry.async_get_entity_id(
            "media_player", DOMAIN, entry.unique_id
        )

    first_api = first_entry.runtime_data.api
    second_api = second_entry.runtime_data.api
    receiver_api = receiver_entry.runtime_data.api
    first_coordinator = first_entry.runtime_data.coordinator
    second_coordinator = second_entry.runtime_data.coordinator
    receiver_coordinator = receiver_entry.runtime_data.coordinator
    first_sender_status_started = asyncio.Event()
    continue_first_join = asyncio.Event()
    receiver_state = {"sender": None}

    async def get_first_sender_status() -> dict[str, str | bool]:
        first_sender_status_started.set()
        await continue_first_join.wait()
        return {"uuid": "first-sender", "enabled": False}

    first_api.async_get_sender_status.reset_mock()
    second_api.async_get_sender_status.reset_mock()
    receiver_api.async_get_sender_status.reset_mock()
    first_api.async_get_sender_status.side_effect = get_first_sender_status
    second_api.async_get_sender_status.return_value = {
        "uuid": "second-sender",
        "enabled": False,
    }
    receiver_api.async_get_sender_status.return_value = {"enabled": False}

    async def get_receiver_state() -> dict[str, str | None]:
        return receiver_state

    async def link_receiver(uuid: str) -> None:
        receiver_state["sender"] = uuid
        receiver_coordinator.data["receiver"] = receiver_state

    async def enable_first_sender(name: str) -> None:
        first_coordinator.data["sender"] = {"enabled": True, "uuid": "first-sender"}

    async def enable_second_sender(name: str) -> None:
        second_coordinator.data["sender"] = {"enabled": True, "uuid": "second-sender"}

    first_api.async_enable_sender.side_effect = enable_first_sender
    second_api.async_enable_sender.side_effect = enable_second_sender
    receiver_api.async_get_receiver_state = AsyncMock(side_effect=get_receiver_state)
    receiver_api.async_receiver_link = AsyncMock(side_effect=link_receiver)

    assert (
        first_entry.runtime_data.group_mutation_lock
        is second_entry.runtime_data.group_mutation_lock
    )
    first_join = asyncio.create_task(
        first_player.async_join_players(
            [
                entity_registry.async_get_entity_id(
                    "media_player", DOMAIN, receiver_entry.unique_id
                )
            ]
        )
    )
    await asyncio.wait_for(first_sender_status_started.wait(), timeout=1)
    second_join = asyncio.create_task(
        second_player.async_join_players(
            [
                entity_registry.async_get_entity_id(
                    "media_player", DOMAIN, receiver_entry.unique_id
                )
            ]
        )
    )

    try:
        await asyncio.sleep(0)
        second_status_was_queried_early = (
            second_api.async_get_sender_status.await_count > 0
        )
    finally:
        continue_first_join.set()
        first_result, second_result = await asyncio.gather(
            first_join, second_join, return_exceptions=True
        )

    assert not second_status_was_queried_early
    assert first_result is None
    assert isinstance(second_result, ServiceValidationError)
    assert second_result.translation_key == "member_already_grouped"
    first_api.async_enable_sender.assert_awaited_once_with("Living room Group")
    second_api.async_enable_sender.assert_not_awaited()
    receiver_api.async_receiver_link.assert_awaited_once_with("first-sender")
    assert receiver_state == {"sender": "first-sender"}


async def test_unjoin_waits_for_in_progress_join(
    make_player: PlayerFactory,
) -> None:
    """Serialize unjoin operations with joins across different entries."""
    first_player, first_entry, first_coordinator, first_api = make_player()
    second_player, second_entry, second_coordinator, second_api = make_player()
    shared_lock = first_entry.runtime_data.group_mutation_lock
    second_entry.runtime_data = AirlinoRuntimeData(
        api=second_api,
        coordinator=second_coordinator,
        group_mutation_lock=shared_lock,
    )
    second_player._group_mutation_lock = shared_lock
    first_sender_status_started = asyncio.Event()
    continue_first_join = asyncio.Event()

    async def get_first_sender_status() -> dict[str, str | bool]:
        first_sender_status_started.set()
        await continue_first_join.wait()
        return {"uuid": "first-sender", "enabled": False}

    first_api.async_get_sender_status.side_effect = get_first_sender_status
    receiver_coordinator = MagicMock()
    receiver_coordinator.data = {"online": True}
    receiver_coordinator.async_request_refresh = AsyncMock()
    runtime = AirlinoRuntimeData(api=second_api, coordinator=receiver_coordinator)
    first_player._async_find_runtime_by_entity_id = AsyncMock(return_value=runtime)

    join_task = asyncio.create_task(
        first_player.async_join_players(["media_player.receiver"])
    )
    await asyncio.wait_for(first_sender_status_started.wait(), timeout=1)
    unjoin_task = asyncio.create_task(second_player.async_unjoin_player())

    try:
        await asyncio.sleep(0)
        unjoin_started_early = second_api.async_receiver_unlink.await_count > 0
    finally:
        continue_first_join.set()
        await asyncio.gather(join_task, unjoin_task)

    assert not unjoin_started_early
    second_api.async_receiver_unlink.assert_awaited_once()
    assert first_coordinator.async_request_refresh.await_count == 1


async def test_empty_or_self_only_join_does_not_query_sender(
    make_player: PlayerFactory,
) -> None:
    """Do not interact with the device when no receivers were requested."""
    player, _, coordinator, api = make_player()
    api.async_get_sender_status.return_value = {"enabled": False}

    await player.async_join_players([])
    await player.async_join_players([player.entity_id])

    api.async_get_sender_status.assert_not_awaited()
    api.async_enable_sender.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_awaited()


async def test_unjoin_sender_does_not_unlink_unrelated_receivers(
    make_player: PlayerFactory,
) -> None:
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


async def test_unjoin_sender_unlinks_receivers_and_disables_sender(
    make_player: PlayerFactory,
) -> None:
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


async def test_unjoin_receiver_only_unlinks_requested_receiver(
    make_player: PlayerFactory,
) -> None:
    """Unlink only the requested receiver without inspecting cached members."""
    player, _, coordinator, api = make_player({"receiver": {"sender": "master-uuid"}})

    await player.async_unjoin_player()

    api.async_receiver_unlink.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited_once()


async def test_offline_member_fails_before_enabling_sender(
    make_player: PlayerFactory,
) -> None:
    """Reject offline group members before changing sender state."""
    player, _, _, api = make_player()
    offline_api = MagicMock()
    offline_coordinator = MagicMock()
    offline_coordinator.data = {"online": False}
    runtime = AirlinoRuntimeData(api=offline_api, coordinator=offline_coordinator)
    player._async_find_runtime_by_entity_id = AsyncMock(return_value=runtime)

    with pytest.raises(ServiceValidationError):
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
    make_player: PlayerFactory, receiver_state: dict, sender_state: dict
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

    with pytest.raises(ServiceValidationError):
        await player.async_join_players(["media_player.kitchen"])

    sender_api.async_enable_sender.assert_not_awaited()
    member_api.async_receiver_unlink.assert_not_awaited()
    member_api.async_receiver_link.assert_not_awaited()
