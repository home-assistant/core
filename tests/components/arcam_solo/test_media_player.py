"""Tests for the Arcam Solo media player entity."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.arcam_solo.media_player import (
    ArcamSoloMediaPlayerEntity,
    async_setup_entry,
)
from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


@pytest.fixture
def entity() -> ArcamSoloMediaPlayerEntity:
    """Create an Arcam Solo media player entity."""
    entry = MockConfigEntry(domain="arcam_solo", data={})
    entry.runtime_data = MagicMock()
    entry.runtime_data.available = True
    entry.runtime_data.source = "CD"
    entry.runtime_data.zones = {1: {"power": "On", "volume": 20, "muted": False}}
    entry.runtime_data.turn_on = AsyncMock()
    entry.runtime_data.turn_off = AsyncMock()
    entry.runtime_data.set_source = AsyncMock()
    entry.runtime_data.set_volume = AsyncMock()
    entry.runtime_data.send_ir_command = AsyncMock()
    return ArcamSoloMediaPlayerEntity(entry)


@pytest.mark.parametrize(
    ("zone_state", "source", "expected_state"),
    [
        (None, None, None),
        ({}, None, None),
        ({"power": "Standby"}, "CD", MediaPlayerState.OFF),
        (
            {"power": "On", "cd_playback_state": "Playing"},
            "CD",
            MediaPlayerState.PLAYING,
        ),
        (
            {"power": "On", "cd_playback_state": "Stopped"},
            "CD",
            MediaPlayerState.IDLE,
        ),
        ({"power": "On"}, "AUX", MediaPlayerState.ON),
    ],
)
def test_state(
    entity: ArcamSoloMediaPlayerEntity,
    zone_state: dict[str, str] | None,
    source: str | None,
    expected_state: MediaPlayerState | str,
) -> None:
    """Test the media player state mapping."""
    entity.arcam_solo.source = source
    entity.arcam_solo.zones = {1: zone_state} if zone_state is not None else {}
    assert entity.state == expected_state


def test_supported_features_for_cd(entity: ArcamSoloMediaPlayerEntity) -> None:
    """Test supported features while CD is active."""
    entity.arcam_solo.source = "CD"
    features = entity.supported_features
    assert features & MediaPlayerEntityFeature.PLAY
    assert features & MediaPlayerEntityFeature.REPEAT_SET
    assert features & MediaPlayerEntityFeature.NEXT_TRACK


def test_supported_features_for_aux(entity: ArcamSoloMediaPlayerEntity) -> None:
    """Test supported features while AUX is active."""
    entity.arcam_solo.source = "AUX"
    features = entity.supported_features
    assert not features & MediaPlayerEntityFeature.PLAY
    assert not features & MediaPlayerEntityFeature.NEXT_TRACK
    assert features & MediaPlayerEntityFeature.SELECT_SOURCE


def test_volume_properties(entity: ArcamSoloMediaPlayerEntity) -> None:
    """Test volume related properties."""
    entity.arcam_solo.zones[1]["volume"] = 36
    entity.arcam_solo.zones[1]["muted"] = True
    assert entity.volume_level == 0.5
    assert entity.is_volume_muted is True


@pytest.mark.parametrize(
    ("repeat_value", "expected_repeat"),
    [("all", RepeatMode.ALL), ("single", RepeatMode.ONE), ("off", RepeatMode.OFF)],
)
def test_repeat_mapping(
    entity: ArcamSoloMediaPlayerEntity, repeat_value: str, expected_repeat: RepeatMode
) -> None:
    """Test repeat property mapping."""
    entity.arcam_solo.source = "CD"
    entity.arcam_solo.zones[1]["repeat"] = repeat_value
    assert entity.repeat == expected_repeat


@pytest.mark.parametrize(
    ("source", "method_name"),
    [
        ("AUX", "async_media_play"),
        ("AUX", "async_media_pause"),
        ("AUX", "async_media_stop"),
        ("AUX", "async_media_next_track"),
        ("AUX", "async_media_previous_track"),
    ],
)
async def test_media_actions_validate_source(
    entity: ArcamSoloMediaPlayerEntity, source: str, method_name: str
) -> None:
    """Test unsupported media actions raise validation error."""
    entity.arcam_solo.source = source
    method = getattr(entity, method_name)
    with pytest.raises(ServiceValidationError):
        await method()


@pytest.mark.parametrize(
    ("source", "method_name", "expected_command"),
    [
        ("CD", "async_media_play", "cd_play"),
        ("CD", "async_media_pause", "cd_pause"),
        ("CD", "async_media_stop", "cd_stop"),
        ("CD", "async_media_next_track", "cd_track_next"),
        ("CD", "async_media_previous_track", "cd_track_previous"),
        ("DAB", "async_media_next_track", "navigate_up"),
        ("FM", "async_media_previous_track", "navigate_down"),
    ],
)
async def test_media_actions_send_expected_ir(
    entity: ArcamSoloMediaPlayerEntity,
    source: str,
    method_name: str,
    expected_command: str,
) -> None:
    """Test supported media actions call the expected IR command."""
    entity.arcam_solo.source = source
    method: Callable[[], Awaitable[None]] = getattr(entity, method_name)
    await method()
    entity.arcam_solo.send_ir_command.assert_awaited_once_with(command=expected_command)
    entity.arcam_solo.send_ir_command.reset_mock()


def test_available_checks_zone_exists(entity: ArcamSoloMediaPlayerEntity) -> None:
    """Test availability checks both transport and zone presence."""
    entity.arcam_solo.available = False
    assert entity.available is False

    entity.arcam_solo.available = True
    entity.arcam_solo.zones = {}
    assert entity.available is False

    entity.arcam_solo.zones = {1: {"power": "On"}}
    assert entity.available is True


def test_source_list_excludes_na(entity: ArcamSoloMediaPlayerEntity) -> None:
    """Test source list does not include placeholder sources."""
    assert "N/A" not in entity.source_list


def test_media_title_branches(entity: ArcamSoloMediaPlayerEntity) -> None:
    """Test media title source-specific behavior."""
    entity.arcam_solo.source = "DAB"
    entity.arcam_solo.zones[1]["radio_station"] = "BBC Radio 1"
    assert entity.media_title == "BBC Radio 1"

    entity.arcam_solo.source = "CD"
    entity.arcam_solo.zones[1]["cd_playback_state"] = "Paused"
    entity.arcam_solo.zones[1]["lsb_current_track"] = 2
    entity.arcam_solo.zones[1]["lsb_total_track"] = 10
    assert entity.media_title == "Track 2 / 10"

    entity.arcam_solo.zones[1]["cd_playback_state"] = "Tray Open / Empty"
    assert entity.media_title == "Tray Open / Empty"

    entity.arcam_solo.source = "AUX"
    assert entity.media_title == "AUX"


def test_media_properties_for_cd(entity: ArcamSoloMediaPlayerEntity) -> None:
    """Test track and position properties for CD/USB."""
    entity.arcam_solo.source = "CD"
    entity.arcam_solo.zones[1]["current_track_position"] = 42
    entity.arcam_solo.zones[1]["lsb_current_track"] = 3
    entity.arcam_solo.zones[1]["lsb_total_track"] = 12

    assert entity.media_position == 42
    assert entity.media_track == 3
    assert entity.media_total_tracks == 12
    assert entity.media_duration is None


def test_media_properties_non_playable_source(
    entity: ArcamSoloMediaPlayerEntity,
) -> None:
    """Test media properties are none when source is not playable."""
    entity.arcam_solo.source = "AUX"
    assert entity.media_position is None
    assert entity.media_track is None
    assert entity.media_total_tracks is None
    assert entity.repeat is None
    assert entity.shuffle is None


def test_shuffle_defaults_false_for_playable_source(
    entity: ArcamSoloMediaPlayerEntity,
) -> None:
    """Test shuffle defaults to false for playable source without value."""
    entity.arcam_solo.source = "CD"
    entity.arcam_solo.zones[1].pop("shuffle", None)
    assert entity.shuffle is False


@pytest.mark.parametrize(
    ("source", "state", "expected_media_type"),
    [
        ("AUX", MediaPlayerState.ON, None),
        ("DAB", MediaPlayerState.ON, MediaType.MUSIC),
        ("CD", MediaPlayerState.PLAYING, MediaType.MUSIC),
        ("CD", MediaPlayerState.ON, None),
    ],
)
def test_media_type(
    entity: ArcamSoloMediaPlayerEntity,
    source: str,
    state: MediaPlayerState,
    expected_media_type: MediaType | None,
) -> None:
    """Test media type mapping across source/state combinations."""
    entity.arcam_solo.source = source
    entity.arcam_solo.zones[1]["power"] = "On"
    if source == "CD":
        entity.arcam_solo.zones[1]["cd_playback_state"] = (
            "Playing" if state == MediaPlayerState.PLAYING else "Tray Open / Empty"
        )
    assert entity.state == state
    assert entity.media_type == expected_media_type


async def test_control_methods(entity: ArcamSoloMediaPlayerEntity) -> None:
    """Test basic control methods dispatch to backend client."""
    await entity.async_turn_on()
    await entity.async_turn_off()
    await entity.async_select_source("FM")
    await entity.async_volume_up()
    await entity.async_volume_down()
    await entity.async_set_volume_level(0.5)
    await entity.async_mute_volume(True)
    await entity.async_mute_volume(False)

    entity.arcam_solo.turn_on.assert_awaited_once()
    entity.arcam_solo.turn_off.assert_awaited_once()
    entity.arcam_solo.set_source.assert_awaited_once_with("FM")
    entity.arcam_solo.set_volume.assert_awaited_once_with(36)
    entity.arcam_solo.send_ir_command.assert_any_await(command="volume_plus")
    entity.arcam_solo.send_ir_command.assert_any_await(command="volume_minus")
    entity.arcam_solo.send_ir_command.assert_any_await(command="mute_on")
    entity.arcam_solo.send_ir_command.assert_any_await(command="mute_off")


@pytest.mark.parametrize(
    ("repeat_mode", "expected_command"),
    [
        (RepeatMode.ALL, "cd_repeat_all"),
        (RepeatMode.ONE, "cd_repeat_single"),
        (RepeatMode.OFF, "cd_repeat_off"),
    ],
)
async def test_async_set_repeat(
    entity: ArcamSoloMediaPlayerEntity,
    repeat_mode: RepeatMode,
    expected_command: str,
) -> None:
    """Test repeat setter sends expected command."""
    await entity.async_set_repeat(repeat_mode)
    entity.arcam_solo.send_ir_command.assert_awaited_once_with(command=expected_command)
    entity.arcam_solo.send_ir_command.reset_mock()


@pytest.mark.parametrize(
    ("shuffle_enabled", "expected_command"),
    [(True, "cd_shuffle_on"), (False, "cd_shuffle_off")],
)
async def test_async_set_shuffle(
    entity: ArcamSoloMediaPlayerEntity, shuffle_enabled: bool, expected_command: str
) -> None:
    """Test shuffle setter sends expected command."""
    await entity.async_set_shuffle(shuffle_enabled)
    entity.arcam_solo.send_ir_command.assert_awaited_once_with(command=expected_command)
    entity.arcam_solo.send_ir_command.reset_mock()


async def test_async_setup_entry_adds_entity(hass: HomeAssistant) -> None:
    """Test platform setup adds the media player entity."""
    entry = MockConfigEntry(domain="arcam_solo", data={})
    entry.runtime_data = MagicMock()
    async_add_entities = MagicMock()

    await async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
