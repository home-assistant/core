"""Tests for the Lyngdorf media player platform."""

from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, datetime
from operator import attrgetter
from typing import Any
from unittest.mock import MagicMock, patch

from lyngdorf import LyngdorfModel
from lyngdorf.states import Control, PlaybackState, Repeat
from lyngdorf.streaming import NowPlaying
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    RepeatMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import notify_position_jump, notify_receiver_update

from tests.common import MockConfigEntry, snapshot_platform

POSITION_UPDATED_AT = datetime(2026, 8, 17, 13, tzinfo=UTC)

MAIN_ZONE = "media_player.mock_lyngdorf_main_zone"
ZONE_B = "media_player.mock_lyngdorf_zone_b"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the media player platform."""
    return [Platform.MEDIA_PLAYER]


@pytest.fixture(autouse=True)
def media_proxy_token() -> Generator[None]:
    """Freeze the media proxy token, which otherwise varies per run."""
    with patch("secrets.token_hex", return_value="mock_token"):
        yield


@pytest.fixture
def playing_receiver(mock_receiver: MagicMock) -> MagicMock:
    """Return a receiver that is streaming a track."""
    mock_receiver.power_on = True
    mock_receiver.player.now_playing = NowPlaying(
        state=PlaybackState.PLAYING,
        title="The Killing Moon",
        artist="Echo & the Bunnymen",
        album="Songs to Learn & Sing",
        source="Total Solar Eclipse Playlist",
        art_url="https://example.test/art.jpg",
        duration_ms=346280,
        controls=frozenset(
            {
                Control.PAUSE,
                Control.NEXT_TRACK,
                Control.PREVIOUS_TRACK,
                Control.SEEK,
            }
        ),
        play_modes=frozenset(),
    )
    mock_receiver.player.position_ms = 318544
    mock_receiver.player.position_updated_at = POSITION_UPDATED_AT
    mock_receiver.player.shuffle = False
    mock_receiver.player.repeat = Repeat.OFF
    mock_receiver.player.can_shuffle = True
    mock_receiver.player.repeat_modes = frozenset({Repeat.OFF, Repeat.ALL})
    return mock_receiver


async def test_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the media player entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_no_zone_b_entity_for_model_without_zone_b(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no Zone B media player entity is created for a model without Zone B."""
    mock_config_entry.add_to_hass(hass)
    mock_receiver.zone_b = None

    with patch(
        "homeassistant.components.lyngdorf.lookup_model",
        return_value=LyngdorfModel.TDAI_3400,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ZONE_B) is None
    assert entity_registry.async_get(ZONE_B) is None
    assert hass.states.get(MAIN_ZONE) is not None


@pytest.mark.parametrize(
    ("entity_id", "service", "attr", "expected"),
    [
        (MAIN_ZONE, SERVICE_TURN_ON, "set_power", True),
        (MAIN_ZONE, SERVICE_TURN_OFF, "set_power", False),
        (ZONE_B, SERVICE_TURN_ON, "zone_b.set_power", True),
        (ZONE_B, SERVICE_TURN_OFF, "zone_b.set_power", False),
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
    attrgetter(attr)(mock_receiver).assert_awaited_once_with(expected)


@pytest.mark.parametrize(
    ("entity_id", "service", "method"),
    [
        (MAIN_ZONE, SERVICE_VOLUME_UP, "volume.up"),
        (MAIN_ZONE, SERVICE_VOLUME_DOWN, "volume.down"),
        (ZONE_B, SERVICE_VOLUME_UP, "zone_b.volume.up"),
        (ZONE_B, SERVICE_VOLUME_DOWN, "zone_b.volume.down"),
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
    attrgetter(method)(mock_receiver).assert_awaited_once()


@pytest.mark.parametrize(
    ("entity_id", "level", "method", "expected_db"),
    [
        (MAIN_ZONE, 0.5, "volume.set", -37.95),
        (MAIN_ZONE, 1.0, "volume.set", 24.0),
        (ZONE_B, 0.3, "zone_b.volume.set", -62.73),
    ],
)
async def test_volume_set(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
    entity_id: str,
    level: float,
    method: str,
    expected_db: float,
) -> None:
    """Test setting and clamping volume on both zones."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: entity_id, ATTR_MEDIA_VOLUME_LEVEL: level},
        blocking=True,
    )
    attrgetter(method)(mock_receiver).assert_awaited_once_with(
        pytest.approx(expected_db)
    )


@pytest.mark.parametrize(
    ("entity_id", "attr"),
    [
        (MAIN_ZONE, "set_muted"),
        (ZONE_B, "zone_b.set_muted"),
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
    attrgetter(attr)(mock_receiver).assert_awaited_once_with(True)


@pytest.mark.parametrize(
    ("entity_id", "attr"),
    [
        (MAIN_ZONE, "set_source"),
        (ZONE_B, "zone_b.set_source"),
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
    attrgetter(attr)(mock_receiver).assert_awaited_once_with("HDMI")


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
    mock_receiver.set_sound_mode.assert_awaited_once_with("Movie")


async def test_availability(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test availability when device disconnects and reconnects."""
    mock_receiver.connected = False
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert hass.states.get(MAIN_ZONE).state == STATE_UNAVAILABLE
    assert hass.states.get(ZONE_B).state == STATE_UNAVAILABLE

    mock_receiver.connected = True
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert hass.states.get(MAIN_ZONE).state != STATE_UNAVAILABLE
    assert hass.states.get(ZONE_B).state != STATE_UNAVAILABLE


async def test_main_zone_state_properties(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test main zone state properties are reported correctly."""
    mock_receiver.power_on = True
    mock_receiver.volume.value = -40.0
    mock_receiver.muted = False
    mock_receiver.source = "HDMI"
    mock_receiver.sound_mode = "Movie"
    mock_receiver.sources = ["HDMI", "Optical"]
    mock_receiver.sound_modes = ["Movie", "Stereo"]
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    state = hass.states.get(MAIN_ZONE)
    assert state.state == MediaPlayerState.ON
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == pytest.approx(0.484, abs=0.01)
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False
    assert state.attributes[ATTR_INPUT_SOURCE] == "HDMI"
    assert state.attributes[ATTR_SOUND_MODE] == "Movie"
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["HDMI", "Optical"]
    assert state.attributes[ATTR_SOUND_MODE_LIST] == ["Movie", "Stereo"]

    mock_receiver.volume.value = None
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()
    state = hass.states.get(MAIN_ZONE)
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) is None

    mock_receiver.power_on = False
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()
    state = hass.states.get(MAIN_ZONE)
    assert state.state == MediaPlayerState.OFF


async def test_zone_b_state_properties(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test zone B state properties are reported correctly."""
    mock_receiver.zone_b.power_on = True
    mock_receiver.zone_b.volume.value = -30.0
    mock_receiver.zone_b.muted = True
    mock_receiver.zone_b.source = "Optical"
    mock_receiver.zone_b.sources = ["HDMI", "Optical"]
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_B)
    assert state.state == MediaPlayerState.ON
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == pytest.approx(0.564, abs=0.01)
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is True
    assert state.attributes[ATTR_INPUT_SOURCE] == "Optical"
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["HDMI", "Optical"]

    mock_receiver.zone_b.volume.value = None
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()
    state = hass.states.get(ZONE_B)
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) is None


async def test_now_playing(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    playing_receiver: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test now-playing metadata, position and transport features while playing."""
    notify_receiver_update(playing_receiver)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.usefixtures("mock_receiver")
async def test_transport_features_absent_when_idle(
    hass: HomeAssistant,
) -> None:
    """Test no transport is offered when nothing is playing."""
    features = hass.states.get(MAIN_ZONE).attributes[ATTR_SUPPORTED_FEATURES]
    assert not features & MediaPlayerEntityFeature.PAUSE
    assert not features & MediaPlayerEntityFeature.SEEK


@pytest.mark.parametrize(
    ("service", "method"),
    [
        pytest.param(SERVICE_MEDIA_PAUSE, "player.pause", id="pause"),
        pytest.param(SERVICE_MEDIA_NEXT_TRACK, "player.next_track", id="next"),
        pytest.param(
            SERVICE_MEDIA_PREVIOUS_TRACK, "player.previous_track", id="previous"
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_transport_actions(
    hass: HomeAssistant,
    playing_receiver: MagicMock,
    service: str,
    method: str,
) -> None:
    """Test transport actions reach the receiver."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MAIN_ZONE},
        blocking=True,
    )
    attrgetter(method)(playing_receiver).assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_seek_converts_to_milliseconds(
    hass: HomeAssistant,
    playing_receiver: MagicMock,
) -> None:
    """Test seek converts the position Home Assistant gives in seconds."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_SEEK,
        {ATTR_ENTITY_ID: MAIN_ZONE, ATTR_MEDIA_SEEK_POSITION: 42.5},
        blocking=True,
    )
    playing_receiver.player.seek.assert_awaited_once_with(42500)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "payload", "method", "expected"),
    [
        pytest.param(
            SERVICE_SHUFFLE_SET,
            {ATTR_MEDIA_SHUFFLE: True},
            "player.set_shuffle",
            True,
            id="shuffle",
        ),
        pytest.param(
            SERVICE_REPEAT_SET,
            {ATTR_MEDIA_REPEAT: RepeatMode.ALL},
            "player.set_repeat",
            Repeat.ALL,
            id="repeat",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_play_mode(
    hass: HomeAssistant,
    playing_receiver: MagicMock,
    service: str,
    payload: dict[str, Any],
    method: str,
    expected: bool | Repeat,
) -> None:
    """Test shuffle and repeat are set on their own axes."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MAIN_ZONE} | payload,
        blocking=True,
    )
    attrgetter(method)(playing_receiver).assert_awaited_once_with(expected)


@pytest.mark.usefixtures("init_integration")
async def test_volume_before_the_device_reports_one(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test the volume control being absent until the device reports a level."""
    mock_receiver.power_on = True
    mock_receiver.volume = None
    # Changed alongside so the assertions below fail if building the state
    # raised rather than merely omitting the volume.
    mock_receiver.muted = True
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    state = hass.states.get(MAIN_ZONE)
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is True
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) is None

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: MAIN_ZONE},
        blocking=True,
    )
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: MAIN_ZONE, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )


@pytest.mark.usefixtures("init_integration")
async def test_transport_features_follow_the_source(
    hass: HomeAssistant,
    playing_receiver: MagicMock,
) -> None:
    """Test only the controls the current source offers are advertised."""
    now_playing = playing_receiver.player.now_playing
    playing_receiver.player.now_playing = replace(
        now_playing, controls=frozenset({Control.PAUSE})
    )
    notify_receiver_update(playing_receiver)
    await hass.async_block_till_done()

    features = hass.states.get(MAIN_ZONE).attributes[ATTR_SUPPORTED_FEATURES]
    assert features & MediaPlayerEntityFeature.PAUSE
    assert not features & MediaPlayerEntityFeature.SEEK
    assert not features & MediaPlayerEntityFeature.NEXT_TRACK
    assert not features & MediaPlayerEntityFeature.PREVIOUS_TRACK


@pytest.mark.usefixtures("init_integration")
async def test_no_streaming_features_on_model_without_streamer(
    hass: HomeAssistant,
    playing_receiver: MagicMock,
) -> None:
    """Test a model with no streaming module offers no transport."""
    playing_receiver.player = None
    notify_receiver_update(playing_receiver)
    await hass.async_block_till_done()

    state = hass.states.get(MAIN_ZONE)
    assert (
        not state.attributes[ATTR_SUPPORTED_FEATURES] & MediaPlayerEntityFeature.PAUSE
    )
    assert state.attributes.get(ATTR_MEDIA_TITLE) is None


@pytest.mark.usefixtures("init_integration")
async def test_no_position_before_the_streamer_reports_one(
    hass: HomeAssistant,
    playing_receiver: MagicMock,
) -> None:
    """Test an attached player that has not yet reported a position."""
    playing_receiver.player.position_ms = None
    notify_receiver_update(playing_receiver)
    await hass.async_block_till_done()

    state = hass.states.get(MAIN_ZONE)
    assert state.attributes.get(ATTR_MEDIA_POSITION) is None
    # The timestamp advances on every poll, so it must not be published alone.
    assert state.attributes.get(ATTR_MEDIA_POSITION_UPDATED_AT) is None


@pytest.mark.usefixtures("init_integration")
async def test_position_jump_updates_state(
    hass: HomeAssistant,
    playing_receiver: MagicMock,
) -> None:
    """Test a position discontinuity refreshes the reported position."""
    playing_receiver.player.position_ms = 1000
    notify_position_jump(playing_receiver, 1000)
    await hass.async_block_till_done()

    state = hass.states.get(MAIN_ZONE)
    assert state.attributes[ATTR_MEDIA_POSITION] == 1
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] == POSITION_UPDATED_AT
