"""Tests for Kii Audio media player entities."""

from copy import deepcopy

import pytest

from homeassistant.components.kii_audio.const import MAX_VOLUME, MIN_VOLUME, VOLUME_STEP
from homeassistant.components.kii_audio.media_player import (
    KiiAudioZoneMediaPlayer,
    async_setup_entry,
)

from .conftest import ZONE_ID, FakeCoordinator, make_zone


def test_media_player_reports_zone_state(coordinator: FakeCoordinator) -> None:
    """Test media player state is derived from zone settings."""
    entity = KiiAudioZoneMediaPlayer(coordinator, coordinator.data["zones"][0])

    assert entity.name is None
    assert entity.state.value == "on"
    assert entity.volume_level == 0.5
    assert entity.is_volume_muted is False
    assert entity.source == "Analogue"


def test_media_player_uses_zone_device_info(coordinator: FakeCoordinator) -> None:
    """Test media player is attached to a zone-level device."""
    entity = KiiAudioZoneMediaPlayer(coordinator, coordinator.data["zones"][0])

    assert entity.device_info["identifiers"] == {("kii_audio", "system-id_zone-id")}
    assert entity.device_info["manufacturer"] == "Kii Audio GmbH"
    assert entity.device_info["model"] == "Kii Seven"
    assert entity.device_info["name"] == "Office"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("spotify", "Spotify Connect"),
        ("qobuzconnect", "Qobuz Connect"),
        ("unknown", "unknown"),
    ],
)
def test_media_player_reports_current_source(source: str, expected: str) -> None:
    """Test current source labels include display-only streaming sources."""
    zone = make_zone(source=source)
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    assert entity.source == expected


def test_media_player_selectable_sources_without_kii_control() -> None:
    """Test selectable sources for zones without Kii Control."""
    zone = make_zone(has_kii_control=False)
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    assert entity.source_list == [
        "Analogue",
        "Digital (Auto)",
        "Digital (XLR)",
        "Digital (KiiLink)",
        "Dante",
    ]


def test_media_player_selectable_sources_with_kii_control() -> None:
    """Test selectable sources for zones with Kii Control."""
    zone = make_zone(has_kii_control=True)
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    assert entity.source_list == [
        "Coax",
        "Optical",
        "USB",
        "Bluetooth",
        "Analogue",
        "Digital (XLR)",
        "Dante",
    ]


@pytest.mark.parametrize(
    ("source", "expected_source_id"),
    [
        ("Digital (Auto)", "digital_auto"),
        ("Digital (XLR)", "digital_xlr"),
        ("digital_kiilink", "digital_kiilink"),
    ],
)
async def test_media_player_select_source_sends_raw_source_id(
    source: str, expected_source_id: str
) -> None:
    """Test selecting a source sends the Kii source ID."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    await entity.async_select_source(source)

    assert coordinator.calls == [("source", (ZONE_ID, expected_source_id))]


async def test_media_player_ignores_unselectable_streaming_source() -> None:
    """Test streaming sources are not selectable from HA."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    await entity.async_select_source("Spotify Connect")

    assert coordinator.calls == []


async def test_media_player_volume_controls() -> None:
    """Test volume control requests."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    await entity.async_set_volume_level(0.75)
    await entity.async_volume_up()
    await entity.async_volume_down()

    assert coordinator.calls == [
        ("volume", (ZONE_ID, -25.0)),
        ("volume", (ZONE_ID, -50.0 + VOLUME_STEP)),
        ("volume", (ZONE_ID, -50.0 - VOLUME_STEP)),
    ]


@pytest.mark.parametrize(
    ("volume", "expected_kii_volume"),
    [
        (-1.0, MIN_VOLUME),
        (2.0, MAX_VOLUME),
    ],
)
async def test_media_player_set_volume_clamps_to_supported_range(
    volume: float, expected_kii_volume: float
) -> None:
    """Test setting volume clamps to the Kii volume range."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    await entity.async_set_volume_level(volume)

    assert coordinator.calls == [("volume", (ZONE_ID, expected_kii_volume))]


def test_zone_device_info_reports_mixed_models() -> None:
    """Test mixed zone models are summarized without hiding the difference."""
    zone = make_zone()
    zone["devices"].append(
        {
            "deviceId": "speaker-2",
            "modelName": "Kii Three",
            "macAddress": "00:11:22:33:44:66",
        }
    )
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    assert entity.device_info["model"] == "Mixed (Kii Seven, Kii Three)"


async def test_media_player_setup_entry_adds_zone_entities(
    coordinator: FakeCoordinator,
) -> None:
    """Test media player setup adds one entity for valid zone data."""
    added_entities: list[KiiAudioZoneMediaPlayer] = []
    config_entry = type("ConfigEntry", (), {"runtime_data": coordinator})()

    def add_entities(entities) -> None:
        added_entities.extend(entities)

    coordinator.data["zones"].append({"zoneId": 1})

    await async_setup_entry(None, config_entry, add_entities)  # type: ignore[arg-type]

    assert len(added_entities) == 1
    assert added_entities[0].unique_id == "system-id_zone-id"


def test_media_player_reports_off_state() -> None:
    """Test media player reports off when zone power is off."""
    zone = make_zone()
    zone["settings"]["power"] = False
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    assert entity.state.value == "off"


def test_media_player_handles_missing_values() -> None:
    """Test media player properties handle missing or invalid values."""
    zone = make_zone()
    zone["settings"]["audio"] = {"volume": "invalid", "source": 1, "mute": "no"}
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    assert entity.volume_level is None
    assert entity.source is None
    assert entity.is_volume_muted is None


async def test_media_player_ignores_volume_steps_without_current_volume() -> None:
    """Test volume step actions are ignored without a numeric current volume."""
    zone = make_zone()
    zone["settings"]["audio"]["volume"] = "invalid"
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    await entity.async_volume_up()
    await entity.async_volume_down()

    assert coordinator.calls == []


async def test_media_player_power_and_mute_controls() -> None:
    """Test power and mute controls send coordinator requests."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    await entity.async_mute_volume(True)
    await entity.async_turn_on()
    await entity.async_turn_off()

    assert coordinator.calls == [
        ("mute", (ZONE_ID, True)),
        ("power", (ZONE_ID, True)),
        ("power", (ZONE_ID, False)),
    ]


def test_media_player_handles_missing_zone() -> None:
    """Test media player falls back when its zone is missing from coordinator data."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)
    coordinator.data["zones"] = []

    assert entity.source_list == [
        "Analogue",
        "Digital (Auto)",
        "Digital (XLR)",
        "Digital (KiiLink)",
        "Dante",
    ]
    assert entity.source is None


def test_media_player_handles_invalid_kiilink_data() -> None:
    """Test Kii Control detection ignores invalid kiilink data."""
    zone = make_zone()
    zone["kiilink"] = []
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    assert entity.source_list == [
        "Analogue",
        "Digital (Auto)",
        "Digital (XLR)",
        "Digital (KiiLink)",
        "Dante",
    ]

    zone["kiilink"] = {"devices": {}}
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    assert entity.source_list == [
        "Analogue",
        "Digital (Auto)",
        "Digital (XLR)",
        "Digital (KiiLink)",
        "Dante",
    ]
