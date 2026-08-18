"""Fixtures for the Lyngdorf integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from lyngdorf.const import LyngdorfModel
from lyngdorf.device import Receiver
from lyngdorf.models.base import NumericRange
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


@pytest.fixture
def mock_receiver() -> Generator[MagicMock]:
    """Return a mocked Lyngdorf receiver."""
    with patch(
        "homeassistant.components.lyngdorf.async_create_receiver"
    ) as create_mock:
        receiver = MagicMock(spec=Receiver)
        receiver.name = "Mock Lyngdorf"
        receiver.connected = True

        # Diagnostics reports the whole receiver, so every property it reads
        # needs a value here; an unset one is a mock the response cannot encode.
        receiver.model = LyngdorfModel.MP_60
        receiver.max_volume = 0.0
        receiver.room_perfect_position = None
        receiver.available_room_perfect_positions = []
        receiver.voicing = None
        receiver.available_voicings = []
        receiver.lipsync = None
        receiver.lipsync_range = NumericRange(0, 500, 1)
        for _t in ("bass", "treble"):
            setattr(receiver, f"trim_{_t}", None)
            setattr(receiver, f"trim_{_t}_range", NumericRange(-12.0, 12.0, 0.1))
        for _t in ("centre", "height", "lfe", "surround"):
            setattr(receiver, f"trim_{_t}", None)
            setattr(receiver, f"trim_{_t}_range", NumericRange(-10.0, 10.0, 0.1))

        receiver.power_on = False
        receiver.volume = -40.0
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
        receiver.available_video_inputs = ["hdmi"]
        receiver.available_stream_types = ["AirPlay", "DLNA"]

        receiver.zone_b_power_on = False
        receiver.zone_b_volume = -40.0
        receiver.zone_b_mute_enabled = False
        receiver.zone_b_source = None
        receiver.zone_b_available_sources = []
        receiver.zone_b_audio_input = "aux"
        receiver.zone_b_streaming_source = "DLNA"

        create_mock.return_value = receiver
        yield receiver


@pytest.fixture
def mock_get_device_serial() -> Generator[AsyncMock]:
    """Return a mocked async_get_device_serial function."""
    with patch(
        "homeassistant.components.lyngdorf.config_flow.async_get_device_serial",
        new=AsyncMock(return_value="0050c27c76b2"),
    ) as serial_mock:
        yield serial_mock


@pytest.fixture
def mock_find_receiver_model() -> Generator[AsyncMock]:
    """Return a mocked async_find_receiver_model function."""
    with patch(
        "homeassistant.components.lyngdorf.config_flow.async_find_receiver_model",
        new=AsyncMock(return_value=LyngdorfModel.MP_60),
    ) as find_mock:
        yield find_mock


def notify_receiver_update(receiver: MagicMock) -> None:
    """Fire every notification callback the entities registered."""
    for call in receiver.register_notification_callback.call_args_list:
        call.args[0]()


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
        patch("homeassistant.components.lyngdorf.lookup_receiver_model") as lookup,
        patch("homeassistant.components.lyngdorf.PLATFORMS", platforms),
    ):
        lookup.return_value = LyngdorfModel.MP_60
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
