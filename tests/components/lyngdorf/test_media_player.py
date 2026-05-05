"""Tests for the Lyngdorf media player platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

MAIN_ZONE = "media_player.mock_lyngdorf_main_zone"
ZONE_B = "media_player.mock_lyngdorf_zone_b"


async def test_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the media player entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "service", "attr", "expected"),
    [
        (MAIN_ZONE, SERVICE_TURN_ON, "power_on", True),
        (MAIN_ZONE, SERVICE_TURN_OFF, "power_on", False),
        (ZONE_B, SERVICE_TURN_ON, "zone_b_power_on", True),
        (ZONE_B, SERVICE_TURN_OFF, "zone_b_power_on", False),
    ],
)
async def test_power(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
    entity_id: str,
    service: str,
    attr: str,
    expected: bool,
) -> None:
    """Test turning power on/off for both zones."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert getattr(mock_receiver, attr) is expected


@pytest.mark.parametrize(
    ("entity_id", "service", "method"),
    [
        (MAIN_ZONE, SERVICE_VOLUME_UP, "volume_up"),
        (MAIN_ZONE, SERVICE_VOLUME_DOWN, "volume_down"),
        (ZONE_B, SERVICE_VOLUME_UP, "zone_b_volume_up"),
        (ZONE_B, SERVICE_VOLUME_DOWN, "zone_b_volume_down"),
    ],
)
async def test_volume_step(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
    entity_id: str,
    service: str,
    method: str,
) -> None:
    """Test volume up/down for both zones."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    getattr(mock_receiver, method).assert_called_once()


@pytest.mark.parametrize(
    ("entity_id", "level", "attr", "expected_db"),
    [
        (MAIN_ZONE, 0.5, "volume", -31.0),
        (MAIN_ZONE, 1.0, "volume", 18.0),
        (ZONE_B, 0.3, "zone_b_volume", -50.6),
    ],
)
async def test_volume_set(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
    entity_id: str,
    level: float,
    attr: str,
    expected_db: float,
) -> None:
    """Test setting and clamping volume on both zones."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: entity_id, ATTR_MEDIA_VOLUME_LEVEL: level},
        blocking=True,
    )
    assert getattr(mock_receiver, attr) == pytest.approx(expected_db)


@pytest.mark.parametrize(
    ("entity_id", "attr"),
    [
        (MAIN_ZONE, "mute_enabled"),
        (ZONE_B, "zone_b_mute_enabled"),
    ],
)
async def test_mute(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
    entity_id: str,
    attr: str,
) -> None:
    """Test muting both zones."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: entity_id, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    assert getattr(mock_receiver, attr) is True


@pytest.mark.parametrize(
    ("entity_id", "attr"),
    [
        (MAIN_ZONE, "source"),
        (ZONE_B, "zone_b_source"),
    ],
)
async def test_select_source(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
    entity_id: str,
    attr: str,
) -> None:
    """Test selecting source on both zones."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: entity_id, ATTR_INPUT_SOURCE: "HDMI"},
        blocking=True,
    )
    assert getattr(mock_receiver, attr) == "HDMI"


async def test_select_sound_mode(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test selecting sound mode on the main zone."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: MAIN_ZONE, ATTR_SOUND_MODE: "Movie"},
        blocking=True,
    )
    assert mock_receiver.sound_mode == "Movie"


async def test_availability(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test availability when device disconnects and reconnects."""
    callbacks = [
        call.args[0]
        for call in mock_receiver.register_notification_callback.call_args_list
    ]
    assert callbacks

    mock_receiver.connected = False
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()

    assert hass.states.get(MAIN_ZONE).state == STATE_UNAVAILABLE
    assert hass.states.get(ZONE_B).state == STATE_UNAVAILABLE

    mock_receiver.connected = True
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()

    assert hass.states.get(MAIN_ZONE).state != STATE_UNAVAILABLE
    assert hass.states.get(ZONE_B).state != STATE_UNAVAILABLE


async def test_main_zone_state_properties(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test main zone state properties are reported correctly."""
    callbacks = [
        call.args[0]
        for call in mock_receiver.register_notification_callback.call_args_list
    ]

    mock_receiver.power_on = True
    mock_receiver.audio_information = "Stereo"
    mock_receiver.video_information = "No video"
    mock_receiver.volume = -40.0
    mock_receiver.mute_enabled = False
    mock_receiver.source = "HDMI"
    mock_receiver.sound_mode = "Movie"
    mock_receiver.available_sources = ["HDMI", "Optical"]
    mock_receiver.available_sound_modes = ["Movie", "Stereo"]
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()

    state = hass.states.get(MAIN_ZONE)
    assert state.state == MediaPlayerState.ON
    assert state.attributes[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert state.attributes[ATTR_MEDIA_TITLE] == "audio: Stereo"
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == pytest.approx(0.408, abs=0.01)
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False
    assert state.attributes[ATTR_INPUT_SOURCE] == "HDMI"
    assert state.attributes[ATTR_SOUND_MODE] == "Movie"
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["HDMI", "Optical"]
    assert state.attributes[ATTR_SOUND_MODE_LIST] == ["Movie", "Stereo"]

    mock_receiver.video_information = "Video"
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()
    state = hass.states.get(MAIN_ZONE)
    assert state.attributes[ATTR_MEDIA_TITLE] == "audio: Stereo video: Video"
    assert state.attributes[ATTR_MEDIA_CONTENT_TYPE] == MediaType.VIDEO

    mock_receiver.audio_information = "No audio"
    mock_receiver.video_information = "No video"
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()
    state = hass.states.get(MAIN_ZONE)
    assert state.state == MediaPlayerState.ON
    assert state.attributes.get(ATTR_MEDIA_TITLE) is None
    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) is None

    mock_receiver.volume = None
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()
    state = hass.states.get(MAIN_ZONE)
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) is None

    mock_receiver.power_on = False
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()
    state = hass.states.get(MAIN_ZONE)
    assert state.state == MediaPlayerState.OFF
    assert state.attributes.get(ATTR_MEDIA_TITLE) is None
    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) is None


async def test_zone_b_state_properties(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test zone B state properties are reported correctly."""
    callbacks = [
        call.args[0]
        for call in mock_receiver.register_notification_callback.call_args_list
    ]

    mock_receiver.zone_b_power_on = True
    mock_receiver.zone_b_volume = -30.0
    mock_receiver.zone_b_mute_enabled = True
    mock_receiver.zone_b_source = "Optical"
    mock_receiver.zone_b_available_sources = ["HDMI", "Optical"]
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_B)
    assert state.state == MediaPlayerState.ON
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == pytest.approx(0.510, abs=0.01)
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is True
    assert state.attributes[ATTR_INPUT_SOURCE] == "Optical"
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["HDMI", "Optical"]

    mock_receiver.zone_b_volume = "invalid"
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()
    state = hass.states.get(ZONE_B)
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) is None
