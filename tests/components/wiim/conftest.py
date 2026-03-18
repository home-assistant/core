"""Pytest fixtures and shared setup for the WiiM integration tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wiim.consts import (
    AudioOutputHwMode,
    DeviceAttribute,
    InputMode,
    LoopMode,
    PlayingStatus,
)
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

WIIM_ENTITY_ID = "media_player.test_wiim_device"


class MockWiimDevice:
    """Test double for a WiimDevice."""

    general_event_callback: Callable[[MockWiimDevice], None] | None
    av_transport_event_callback: Callable[[object, list[object]], None] | None
    rendering_control_event_callback: Callable[[object, list[object]], None] | None
    play_queue_event_callback: Callable[[object, list[object]], None] | None

    def __init__(
        self,
        *,
        udn: str = "uuid:test-udn-1234",
        name: str = "Test WiiM Device",
    ) -> None:
        """Initialize the mock device with the default WiiM test state."""
        self.udn = udn
        self.name = name
        self._model_name = "WiiM Pro"
        self.model_name = "WiiM Pro"
        self.manufacturer = "Linkplay Tech"
        self.firmware_version = "4.8.523456"
        self.ip_address = "192.168.1.100"
        self.http_api_url = "http://192.168.1.100:8080"
        self.presentation_url = "http://192.168.1.100:8080/web_interface"
        self.available = True
        self.model = "WiiM Pro"
        self.volume = 50
        self.is_muted = False
        self.supports_http_api = False
        self.playing_status = PlayingStatus.STOPPED
        self.loop_mode = LoopMode.SHUFFLE_DISABLE_REPEAT_NONE
        self.loop_state = WiimLoopState(
            repeat=WiimRepeatMode.OFF,
            shuffle=False,
        )
        self.input_mode = InputMode.LINE_IN
        self.audio_output_hw_mode = AudioOutputHwMode.SPEAKER_OUT.display_name  # type: ignore[attr-defined]
        self.mac_address = "AA:BB:CC:DD:EE:FF"
        self.current_track_info = {}
        self.current_media = None
        self.current_track_duration = 0
        self.play_mode = "Network"
        self.equalizer_mode = ""
        self.current_position = 0
        self.next_track_uri = ""
        self.event_data: dict[str, str] = {}
        self.general_event_callback = None
        self.av_transport_event_callback = None
        self.rendering_control_event_callback = None
        self.play_queue_event_callback = None
        self._device_info_properties = ""
        self._player_properties = ""
        self._manufacturer = "Linkplay Tech"
        self.output_mode = "speaker"
        self.supported_input_modes = (InputMode.LINE_IN.display_name,)  # type: ignore[attr-defined]
        self.supported_output_modes = (
            AudioOutputHwMode.SPEAKER_OUT.display_name,  # type: ignore[attr-defined]
        )

        self.upnp_device = MagicMock()
        self.upnp_device.udn = self.udn
        self.upnp_device.friendly_name = self.name
        self.upnp_device.model_name = self.model_name
        self.upnp_device.manufacturer = self.manufacturer
        self.upnp_device.serial_number = "TESTSERIAL123"
        self.upnp_device.presentation_url = self.presentation_url
        self.upnp_device.get_device_info = MagicMock(
            return_value={
                "udn": self.udn,
                "friendly_name": self.name,
                "model_name": self.model_name,
                "manufacturer": self.manufacturer,
                "serial_number": self.upnp_device.serial_number,
            }
        )

        self.init_services_and_subscribe = AsyncMock()
        self.disconnect = AsyncMock()
        self.set_available = MagicMock()
        self.ensure_subscriptions = AsyncMock()
        self.get_audio_output_hw_mode = AsyncMock(return_value="speaker")
        self.async_play = AsyncMock()
        self.async_pause = AsyncMock()
        self.async_stop = AsyncMock()
        self.async_next = AsyncMock()
        self.async_previous = AsyncMock()
        self.async_seek = AsyncMock()
        self.async_set_volume = AsyncMock()
        self.async_set_mute = AsyncMock()
        self.async_set_play_mode = AsyncMock()
        self.async_set_output_mode = AsyncMock()
        self.async_set_loop_mode = AsyncMock()
        self.async_play_queue_with_index = AsyncMock()
        self.play_preset = AsyncMock()
        self.play_url = AsyncMock()
        self._http_command_ok = AsyncMock(return_value=True)

        self.async_update = AsyncMock()
        self.async_get_play_queue = AsyncMock(return_value=[])
        self.async_get_audio_output_modes = AsyncMock(return_value=[])
        self.async_get_input_modes = AsyncMock(return_value=[])
        self.async_get_play_mediums = AsyncMock(return_value=[])
        self.sync_device_duration_and_position = AsyncMock()
        self.async_get_transport_capabilities = AsyncMock(
            return_value=WiimTransportCapabilities(
                can_next=False,
                can_previous=False,
                can_repeat=False,
                can_shuffle=False,
            )
        )
        self.async_get_presets = AsyncMock(return_value=())
        self.async_get_queue_snapshot = AsyncMock(
            return_value=WiimQueueSnapshot(items=())
        )
        self.build_loop_mode = MagicMock(
            return_value=LoopMode.SHUFFLE_DISABLE_REPEAT_NONE
        )

    async def fire_general_update(self, hass: HomeAssistant) -> None:
        """Trigger the registered general update callback."""
        assert self.general_event_callback is not None
        self.general_event_callback(self)
        await hass.async_block_till_done()

    async def fire_transport_update(
        self,
        hass: HomeAssistant,
        transport_state: PlayingStatus,
    ) -> None:
        """Trigger the registered AVTransport callback."""
        assert self.av_transport_event_callback is not None
        self.event_data = {"TransportState": transport_state.value}
        self.av_transport_event_callback(MagicMock(), [])
        await hass.async_block_till_done()


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.wiim.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Mock Home Assistant ConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        title="Test WiiM Device",
        unique_id="uuid:test-udn-1234",
    )


@pytest.fixture
def mock_wiim_device() -> MockWiimDevice:
    """Mock a WiimDevice instance."""
    return MockWiimDevice()


@pytest.fixture
def mock_upnp_device():
    """Mock UpnpDevice for zeroconf discovery."""
    upnp_device = MagicMock()
    upnp_device.udn = "uuid:test-udn-1234"
    upnp_device.friendly_name = "Test WiiM Device"
    upnp_device.model_name = "WiiM Pro"
    upnp_device.device_type = "urn:schemas-upnp-org:device:MediaRenderer:1"
    upnp_device.presentation_url = "http://192.168.1.100:8080/web_interface"
    upnp_device.device_url = "http://192.168.1.100:49152/description.xml"
    upnp_device.services = {}
    return upnp_device


@pytest.fixture
def mock_upnp_factory(mock_upnp_device):
    """Mock UpnpFactory for creating devices."""
    factory = MagicMock()
    factory.async_create_device = AsyncMock(return_value=mock_upnp_device)
    return factory


@pytest.fixture
def mock_wiim_api_endpoint():
    """Mock WiimApiEndpoint for HTTP validation."""
    api_endpoint = AsyncMock()
    api_endpoint.json_request = AsyncMock(
        return_value={
            "uuid": "uuid:test-udn-1234",
            "deviceName": "Test WiiM Device",
            "project": "WiiM Pro",
        }
    )
    api_endpoint.get_device_attributes = AsyncMock(
        return_value={
            DeviceAttribute.MAC_ADDRESS: "AA:BB:CC:DD:EE:FF",
        }
    )
    return api_endpoint


@pytest.fixture
def mock_wiim_controller(mock_wiim_device: MockWiimDevice):
    """Mock a WiimController instance."""
    controller = MagicMock()
    controller.add_device = AsyncMock()
    controller.disconnect = AsyncMock()
    controller.remove_device = AsyncMock()
    controller.async_update_all_multiroom_status = AsyncMock()
    controller.get_group_snapshot.return_value = WiimGroupSnapshot(
        role=WiimGroupRole.STANDALONE,
        leader_udn=mock_wiim_device.udn,
        member_udns=(mock_wiim_device.udn,),
    )
    controller.get_device.side_effect = lambda _udn: mock_wiim_device
    return controller


@pytest.fixture
async def init_wiim_media_player(
    hass: HomeAssistant,
    mock_config_entry,
    mock_wiim_device: MockWiimDevice,
    mock_wiim_controller: MagicMock,
) -> None:
    """Set up the WiiM integration."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.wiim.WiimController",
            return_value=mock_wiim_controller,
        ),
        patch(
            "homeassistant.components.wiim.async_create_wiim_device",
            AsyncMock(return_value=mock_wiim_device),
        ),
        patch(
            "homeassistant.components.wiim.get_url",
            return_value="http://192.168.1.10:8123",
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


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
