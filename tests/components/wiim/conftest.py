"""Pytest fixtures and shared setup for the WiiM integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wiim.consts import AudioOutputHwMode, InputMode, LoopMode, PlayingStatus
from wiim.controller import WiimController
from wiim.models import (
    WiimGroupRole,
    WiimGroupSnapshot,
    WiimLoopState,
    WiimProbeResult,
    WiimQueueSnapshot,
    WiimRepeatMode,
    WiimTransportCapabilities,
)

from homeassistant.components.wiim import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.wiim.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock Home Assistant ConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        title="Test WiiM Device",
        unique_id="uuid:test-udn-1234",
    )


@pytest.fixture
def mock_wiim_device() -> Generator[AsyncMock]:
    """Patch async_create_wiim_device and return the mocked WiimDevice instance."""
    with patch(
        "homeassistant.components.wiim.async_create_wiim_device",
        autospec=True,
    ) as mock_create:
        mock = mock_create.return_value
        mock.udn = "uuid:test-udn-1234"
        mock.name = "Test WiiM Device"
        mock.model_name = "WiiM Pro"
        mock.manufacturer = "Linkplay Tech"
        mock.firmware_version = "4.8.523456"
        mock.ip_address = "192.168.1.100"
        mock.http_api_url = "http://192.168.1.100:8080"
        mock.presentation_url = "http://192.168.1.100:8080/web_interface"
        mock.available = True
        mock.model = "WiiM Pro"
        mock.volume = 50
        mock.is_muted = False
        mock.supports_http_api = False
        mock.playing_status = PlayingStatus.STOPPED
        mock.loop_mode = LoopMode.SHUFFLE_DISABLE_REPEAT_NONE
        mock.loop_state = WiimLoopState(
            repeat=WiimRepeatMode.OFF,
            shuffle=False,
        )
        mock.input_mode = InputMode.LINE_IN
        mock.audio_output_hw_mode = AudioOutputHwMode.SPEAKER_OUT.display_name  # type: ignore[attr-defined]
        mock.mac_address = "AA:BB:CC:DD:EE:FF"
        mock.current_track_info = {}
        mock.current_media = None
        mock.current_track_duration = 0
        mock.play_mode = "Network"
        mock.equalizer_mode = ""
        mock.current_position = 0
        mock.next_track_uri = ""
        mock.event_data = {}
        mock.general_event_callback = None
        mock.av_transport_event_callback = None
        mock.rendering_control_event_callback = None
        mock.play_queue_event_callback = None
        mock.output_mode = "speaker"
        mock.supported_input_modes = (InputMode.LINE_IN.display_name,)  # type: ignore[attr-defined]
        mock.supported_output_modes = (
            AudioOutputHwMode.SPEAKER_OUT.display_name,  # type: ignore[attr-defined]
        )

        upnp_device = MagicMock()
        upnp_device.udn = mock.udn
        upnp_device.friendly_name = mock.name
        upnp_device.model_name = mock.model_name
        upnp_device.manufacturer = mock.manufacturer
        upnp_device.serial_number = "TESTSERIAL123"
        upnp_device.presentation_url = mock.presentation_url
        upnp_device.get_device_info = MagicMock(
            return_value={
                "udn": mock.udn,
                "friendly_name": mock.name,
                "model_name": mock.model_name,
                "manufacturer": mock.manufacturer,
                "serial_number": upnp_device.serial_number,
            }
        )
        mock.upnp_device = upnp_device

        mock.get_audio_output_hw_mode = AsyncMock(return_value="speaker")
        mock.async_get_play_queue = AsyncMock(return_value=[])
        mock.async_get_audio_output_modes = AsyncMock(return_value=[])
        mock.async_get_input_modes = AsyncMock(return_value=[])
        mock.async_get_play_mediums = AsyncMock(return_value=[])
        mock.async_get_transport_capabilities = AsyncMock(
            return_value=WiimTransportCapabilities(
                can_next=False,
                can_previous=False,
                can_repeat=False,
                can_shuffle=False,
            )
        )
        mock.async_get_presets = AsyncMock(return_value=())
        mock.async_get_queue_snapshot = AsyncMock(
            return_value=WiimQueueSnapshot(items=())
        )
        mock.build_loop_mode = MagicMock(
            return_value=LoopMode.SHUFFLE_DISABLE_REPEAT_NONE
        )

        yield mock


@pytest.fixture
def mock_wiim_controller(mock_wiim_device: AsyncMock) -> Generator[MagicMock]:
    """Mock a WiimController instance."""
    mock = MagicMock(spec=WiimController)
    mock.add_device = AsyncMock()
    mock.disconnect = AsyncMock()
    mock.remove_device = AsyncMock()
    mock.async_update_all_multiroom_status = AsyncMock()
    mock.get_group_snapshot.return_value = WiimGroupSnapshot(
        role=WiimGroupRole.STANDALONE,
        leader_udn=mock_wiim_device.udn,
        member_udns=(mock_wiim_device.udn,),
    )
    mock.get_device.side_effect = lambda _udn: mock_wiim_device
    with patch(
        "homeassistant.components.wiim.WiimController",
        return_value=mock,
    ):
        yield mock


@pytest.fixture
def mock_probe_player() -> Generator[AsyncMock]:
    """Mock a WiimProbePlayer instance."""
    with patch(
        "homeassistant.components.wiim.config_flow.async_probe_wiim_device"
    ) as mock_probe:
        mock_probe.return_value = WiimProbeResult(
            host="192.168.1.100",
            udn="uuid:test-udn-1234",
            name="WiiM Pro",
            location="http://192.168.1.100:49152/description.xml",
            model="WiiM Pro",
        )
        yield mock_probe
