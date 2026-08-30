"""Fixtures for the Lyngdorf integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Self
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from lyngdorf import (
    LyngdorfModel,
    LyngdorfReceiver,
    NumericControl,
    NumericRange,
    Player,
    Remote,
    RemoteKey,
    Trim,
    ZoneB,
)
import pytest

from homeassistant.components.lyngdorf.const import (
    CONF_SERIAL_NUMBER,
    DOMAIN,
    PLATFORMS,
)
from homeassistant.const import CONF_HOST, CONF_MODEL, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def ssdp_scanner_mock() -> Generator[Mock]:
    """Mock the SSDP Scanner."""
    with patch("homeassistant.components.ssdp.Scanner", autospec=True) as mock_scanner:
        reg_callback = mock_scanner.return_value.async_register_callback
        reg_callback.return_value = Mock(return_value=None)
        yield mock_scanner.return_value


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Mock Lyngdorf",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_MODEL: "MP-60",
            CONF_SERIAL_NUMBER: "0050c27c76b2",
        },
        unique_id="0050c27c76b2",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.lyngdorf.async_setup_entry", return_value=True
    ):
        yield


class _FloatControl(float):
    """A float that is also a control, as the library's 1.x values are."""

    def __new__(cls, value: float, value_range: NumericRange) -> Self:
        """Return a float carrying the control interface alongside it."""
        control = super().__new__(cls, value)
        control.value = value
        control.range = value_range
        control.up = AsyncMock()
        control.down = AsyncMock()
        control.set = AsyncMock()
        return control


def _control(value: float | None, value_range: NumericRange) -> MagicMock:
    """Return a mocked numeric control."""
    control = MagicMock(spec=NumericControl)
    control.value = value
    control.range = value_range
    return control


@pytest.fixture
def mock_create_receiver() -> Generator[MagicMock]:
    """Return a mocked create_receiver factory."""
    with patch("homeassistant.components.lyngdorf.create_receiver") as create_mock:
        yield create_mock


@pytest.fixture
def mock_receiver(mock_create_receiver: MagicMock) -> MagicMock:
    """Return a mocked Lyngdorf receiver."""
    receiver = MagicMock(spec=LyngdorfReceiver)
    receiver.name = "Mock Lyngdorf"
    receiver.connected = True
    receiver.has_remote_keys = True
    receiver.available_remote_keys = frozenset(
        {
            RemoteKey.UP,
            RemoteKey.DOWN,
            RemoteKey.ENTER,
            RemoteKey.MENU,
            RemoteKey.DIGIT_0,
        }
    )
    remote = MagicMock(spec=Remote)
    remote.keys = receiver.available_remote_keys
    receiver.remote = remote

    # Diagnostics reports the whole receiver, so every property it reads
    # needs a value here; an unset one is a mock the response cannot encode.
    receiver.model = LyngdorfModel.MP_60
    receiver.room_perfect_position = "Focus 1"
    receiver.available_room_perfect_positions = ["Global", "Focus 1"]
    receiver.room_perfect_positions = ["Global", "Focus 1"]
    receiver.voicing = "Neutral"
    receiver.available_voicings = ["Neutral", "Music", "Movie"]
    receiver.voicings = ["Neutral", "Music", "Movie"]
    # Sync on the pinned library: they return None rather than a coroutine.
    receiver.set_voicing.return_value = None
    receiver.set_room_perfect_position.return_value = None
    receiver.lipsync = None
    receiver.lipsync_range = NumericRange(0, 500, 1)
    for _t in ("bass", "treble"):
        setattr(receiver, f"trim_{_t}", None)
        setattr(receiver, f"trim_{_t}_range", NumericRange(-12.0, 12.0, 0.1))
    for _t in ("centre", "height", "lfe", "surround"):
        setattr(receiver, f"trim_{_t}", None)
        setattr(receiver, f"trim_{_t}_range", NumericRange(-10.0, 10.0, 0.1))

    receiver.volume_range = NumericRange(-99.9, 24.0, 0.1)
    receiver.zone_b_volume_range = NumericRange(-99.9, 24.0, 0.1)

    receiver.power_on = False
    receiver.volume = _FloatControl(-40.0, NumericRange(-99.9, 24.0, 0.1))
    receiver.muted = False
    receiver.sources = []
    receiver.sound_modes = []
    receiver.mute_enabled = False
    receiver.source = None
    receiver.available_sources = []
    receiver.sound_mode = None
    receiver.available_sound_modes = []

    receiver.audio_information = "Stereo"
    receiver.video_information = "4K HDR"
    receiver.audio_input = "optical"
    receiver.video_input = "hdmi"
    receiver.streaming_source = "AirPlay"
    receiver.available_audio_inputs = ["optical", "aux"]
    receiver.audio_inputs = ["optical", "aux"]
    receiver.available_video_inputs = ["hdmi"]
    receiver.video_inputs = ["hdmi"]
    receiver.available_stream_types = ["AirPlay", "DLNA"]
    receiver.stream_types = ["AirPlay", "DLNA"]

    receiver.now_playing = None
    receiver.has_position = False
    receiver.position_ms = None
    receiver.position_updated_at = None
    receiver.can_shuffle = False
    receiver.available_repeat_modes = frozenset()

    receiver.lipsync = _FloatControl(50.0, NumericRange(0, 500, 1))
    receiver.lipsync_range = NumericRange(0, 500, 1)
    receiver.trims = {
        Trim.BASS: _control(3.0, NumericRange(-12.0, 12.0, 0.1)),
        Trim.TREBLE: _control(0.0, NumericRange(-12.0, 12.0, 0.1)),
        Trim.CENTER: _control(0.0, NumericRange(-10.0, 10.0, 0.1)),
        Trim.HEIGHT: _control(4.0, NumericRange(-10.0, 10.0, 0.1)),
        Trim.LFE: _control(3.0, NumericRange(-10.0, 10.0, 0.1)),
        Trim.SURROUND: _control(0.0, NumericRange(-10.0, 10.0, 0.1)),
    }
    receiver.trim_bass = 3.0
    receiver.trim_treble = 0.0
    receiver.trim_centre = 0.0
    receiver.trim_height = 4.0
    receiver.trim_lfe = 3.0
    receiver.trim_surround = 0.0
    receiver.trim_bass_range = NumericRange(-12.0, 12.0, 0.1)
    receiver.trim_treble_range = NumericRange(-12.0, 12.0, 0.1)
    for _trim in ("centre", "height", "lfe", "surround"):
        setattr(receiver, f"trim_{_trim}_range", NumericRange(-10.0, 10.0, 0.1))

    receiver.zone_b_power_on = False
    receiver.zone_b_volume = -40.0
    receiver.zone_b_mute_enabled = False
    receiver.zone_b_source = None
    receiver.zone_b_available_sources = []
    receiver.zone_b_audio_input = "aux"
    zone_b = MagicMock(spec=ZoneB)
    zone_b.audio_input = "aux"
    zone_b.streaming_source = "DLNA"
    receiver.zone_b = zone_b
    receiver.zone_b_streaming_source = "DLNA"

    receiver.volume = _FloatControl(-40.0, NumericRange(-99.9, 24.0, 0.1))
    receiver.muted = False
    receiver.sources = []
    receiver.sound_modes = []
    receiver.audio_inputs = ["optical", "aux"]
    receiver.video_inputs = ["hdmi"]
    receiver.stream_types = ["AirPlay", "DLNA"]
    receiver.room_perfect_positions = ["Global", "Focus 1"]
    receiver.voicings = ["Neutral", "Music", "Movie"]
    player = MagicMock(spec=Player)
    player.now_playing = None
    player.position_ms = None
    player.position_updated_at = None
    player.shuffle = None
    player.repeat = None
    player.can_shuffle = False
    player.repeat_modes = frozenset()
    receiver.player = player

    zone_b = MagicMock(spec=ZoneB)
    zone_b.power_on = False
    zone_b.muted = False
    zone_b.source = None
    zone_b.audio_input = "aux"
    zone_b.streaming_source = "DLNA"
    zone_b.sources = []
    zone_b.volume = _FloatControl(-40.0, NumericRange(-99.9, 24.0, 0.1))
    receiver.zone_b = zone_b

    mock_create_receiver.return_value = receiver
    return receiver


@pytest.fixture
def mock_get_device_serial() -> Generator[AsyncMock]:
    """Return a mocked fetch_device_serial function."""
    with (
        patch(
            "homeassistant.components.lyngdorf.config_flow.discover_ssdp_location",
            new=AsyncMock(return_value="http://127.0.0.1:8080/desc.xml"),
        ),
        patch(
            "homeassistant.components.lyngdorf.config_flow.fetch_device_serial",
            new=AsyncMock(return_value="0050c27c76b2"),
        ) as serial_mock,
    ):
        yield serial_mock


@pytest.fixture
def mock_find_receiver_model() -> Generator[AsyncMock]:
    """Return a mocked discover_model function."""
    with patch(
        "homeassistant.components.lyngdorf.config_flow.discover_model",
        new=AsyncMock(return_value=LyngdorfModel.MP_60),
    ) as find_mock:
        yield find_mock


def notify_receiver_update(receiver: MagicMock) -> None:
    """Fire every notification callback the entities registered."""
    for call in receiver.on_change.call_args_list:
        call.args[0]()


def notify_position_jump(receiver: MagicMock, position_ms: int | None) -> None:
    """Fire every position jump callback the entities registered."""
    for call in receiver.player.on_position_jump.call_args_list:
        call.args[0](position_ms)


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms to load; override per module to isolate a single platform."""
    return list(PLATFORMS)


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Lyngdorf integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.lyngdorf.lookup_model") as lookup,
        patch("homeassistant.components.lyngdorf.PLATFORMS", platforms),
    ):
        lookup.return_value = LyngdorfModel.MP_60
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
