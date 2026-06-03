"""Tests for Kii Audio media player entities."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.kii_audio.const import (
    CONF_SYSTEM_ID,
    DOMAIN,
    MAX_VOLUME,
    MIN_VOLUME,
    VOLUME_STEP,
)
from homeassistant.components.kii_audio.coordinator import KiiAudioCoordinator
from homeassistant.components.kii_audio.media_player import KiiAudioZoneMediaPlayer
from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .conftest import SYSTEM_ID, ZONE_ID, FakeCoordinator, make_zone

from tests.common import MockConfigEntry


def test_media_player_reports_zone_state(coordinator: FakeCoordinator) -> None:
    """Test media player state is derived from zone settings."""
    entity = KiiAudioZoneMediaPlayer(coordinator, coordinator.data["zones"][0])

    assert entity.name is None
    assert entity.device_class is MediaPlayerDeviceClass.SPEAKER
    assert entity.state.value == "on"
    assert entity.volume_level == 0.5
    assert entity.is_volume_muted is False
    assert entity.source == "Analog"


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
        "Analog",
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
        "Analog",
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
    hass: HomeAssistant,
) -> None:
    """Test media player setup adds one entity for valid zone data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kii Audio",
        data={CONF_HOST: "192.0.2.1", CONF_SYSTEM_ID: SYSTEM_ID},
        unique_id=SYSTEM_ID,
    )
    entry.add_to_hass(hass)

    async def async_wait_ready(coordinator: KiiAudioCoordinator) -> None:
        coordinator.async_set_updated_data(
            {"systemName": "Kii System", "zones": [make_zone(), {"zoneId": 1}]}
        )

    with (
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioClient.start",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_wait_ready",
            new=async_wait_ready,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("media_player.office")
    assert state is not None
    assert state.attributes["friendly_name"] == "Office"


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
        "Analog",
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
        "Analog",
        "Digital (Auto)",
        "Digital (XLR)",
        "Digital (KiiLink)",
        "Dante",
    ]

    zone["kiilink"] = {"devices": {}}
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    assert entity.source_list == [
        "Analog",
        "Digital (Auto)",
        "Digital (XLR)",
        "Digital (KiiLink)",
        "Dante",
    ]


def test_media_player_unique_id_falls_back_to_entry_id() -> None:
    """Test media player unique ID falls back to the entry ID."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))
    coordinator.config_entry.unique_id = None
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    assert entity.unique_id == "entry-id_zone-id"


def test_media_player_ignores_boolean_volume() -> None:
    """Test boolean volume values are ignored."""
    zone = make_zone()
    zone["settings"]["audio"]["volume"] = True
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    assert entity.volume_level is None


async def test_media_player_ignores_boolean_volume_steps() -> None:
    """Test volume step actions ignore boolean volume values."""
    zone = make_zone()
    zone["settings"]["audio"]["volume"] = False
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneMediaPlayer(coordinator, zone)

    await entity.async_volume_up()
    await entity.async_volume_down()

    assert coordinator.calls == []
