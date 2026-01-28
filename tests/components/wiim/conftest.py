"""Pytest fixtures and shared setup for the WiiM integration tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wiim.consts import (
    AudioOutputHwMode,
    DeviceAttribute,
    InputMode,
    LoopMode,
    PlayingStatus,
)
from wiim.wiim_device import WiimDevice

from homeassistant.components.wiim.const import DOMAIN
from homeassistant.components.wiim.media_player import WiimMediaPlayerEntity
from homeassistant.config_entries import SOURCE_USER, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback


@pytest.fixture(autouse=True)
def mock_sdk_logger():
    """Mocks the SDK_LOGGER to prevent actual logging and allow assertion of calls."""
    with (
        patch("homeassistant.components.wiim.const.SDK_LOGGER.warning") as mock_warning,
        patch("homeassistant.components.wiim.const.SDK_LOGGER.debug") as mock_debug,
        patch("homeassistant.components.wiim.const.SDK_LOGGER.info") as mock_info,
        patch("homeassistant.components.wiim.const.SDK_LOGGER.error") as mock_error,
    ):
        yield mock_warning, mock_debug, mock_info, mock_error


@pytest.fixture
def mock_hass() -> HomeAssistant:
    """Mock HomeAssistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries = MagicMock()
    hass.config_entries.async_setup_platforms = AsyncMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.data = {}

    hass.bus = MagicMock()
    hass.bus.async_listen_once = AsyncMock()

    hass.config_entries.flow = MagicMock()
    hass.config_entries.flow.async_init = AsyncMock(
        return_value=MagicMock(flow_id="mock_flow_id", type="form")
    )
    hass.config_entries.flow.async_configure = AsyncMock(
        return_value=MagicMock(flow_id="mock_flow_id", type="form")
    )
    hass.config_entries.flow.async_step = AsyncMock(
        return_value=MagicMock(flow_id="mock_flow_id", type="form")
    )

    hass.helpers = MagicMock()
    hass.helpers.entity_platform = MagicMock()
    hass.helpers.entity_platform.async_get_current_platform = AsyncMock(
        return_value=MagicMock(platform_name=DOMAIN)
    )

    hass.helpers.device_registry = MagicMock()
    hass.config = MagicMock()
    hass.config.is_safe_mode = False
    hass.bus.async_fire = AsyncMock()

    return hass


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Mock Home Assistant ConfigEntry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = "wiim"
    entry.platforms = set()
    entry.title = "Test WiiM Device"
    entry.data = {
        "host": "192.168.1.100",
        "udn": "uuid:test-udn-1234",
        "name": "Test WiiM Device",
        "upnp_location": "http://192.168.1.100:49152/description.xml",
    }
    entry.options = {}
    entry.add_update_listener = MagicMock()
    entry.async_on_unload = MagicMock()
    entry.runtime_data = None
    entry.source = SOURCE_USER
    entry.state = ConfigEntryState.LOADED
    return entry


@pytest.fixture
def mock_add_entities() -> AddEntitiesCallback:
    """Mock the add_entities callback."""
    return AsyncMock()


@pytest.fixture
def mock_wiim_device() -> WiimDevice:
    """Mock a WiimDevice instance."""
    wiim_device = MagicMock(spec=WiimDevice)
    wiim_device.udn = "uuid:test-udn-1234"
    wiim_device.name = "Test WiiM Device"
    wiim_device._model_name = "WiiM Pro"
    wiim_device.model_name = "WiiM Pro"
    wiim_device.manufacturer = "Linkplay Tech"
    wiim_device.firmware_version = "4.8.523456"
    wiim_device.ip_address = "192.168.1.100"
    wiim_device.http_api_url = "http://192.168.1.100:8080"
    wiim_device.available = True
    wiim_device.model = "WiiM Pro"
    wiim_device.volume = 50
    wiim_device.is_muted = False
    wiim_device.supports_http_api = False
    wiim_device.playing_status = PlayingStatus.STOPPED
    wiim_device.loop_mode = LoopMode.SHUFFLE_DISABLE_REPEAT_NONE
    wiim_device.input_mode = InputMode.LINE_IN
    wiim_device.audio_output_hw_mode = AudioOutputHwMode.SPEAKER_OUT.display_name  # type: ignore[attr-defined]
    wiim_device.mac_address = "AA:BB:CC:DD:EE:FF"
    wiim_device.current_track_info = {}
    wiim_device.current_track_duration = 0
    wiim_device.play_mode = "Network"
    wiim_device.equalizer_mode = ""
    wiim_device.current_position = 0
    wiim_device.next_track_uri = ""
    wiim_device._device_info_properties = ""
    wiim_device._player_properties = ""
    wiim_device._manufacturer = "Linkplay Tech"
    wiim_device.output_mode = "speaker"

    wiim_device.upnp_device = MagicMock()
    wiim_device.upnp_device.udn = wiim_device.udn
    wiim_device.upnp_device.friendly_name = wiim_device.name
    wiim_device.upnp_device.model_name = wiim_device.model_name
    wiim_device.upnp_device.manufacturer = wiim_device.manufacturer
    wiim_device.upnp_device.serial_number = "TESTSERIAL123"
    wiim_device.upnp_device.get_device_info = MagicMock(
        return_value={
            "udn": wiim_device.udn,
            "friendly_name": wiim_device.name,
            "model_name": wiim_device.model_name,
            "manufacturer": wiim_device.manufacturer,
            "serial_number": wiim_device.upnp_device.serial_number,
        }
    )
    wiim_device.init_services_and_subscribe = AsyncMock()
    wiim_device.disconnect = AsyncMock()
    wiim_device.play_preset = AsyncMock()
    wiim_device.play_url = AsyncMock()
    wiim_device._http_command_ok = AsyncMock(return_value=True)

    wiim_device.async_update = AsyncMock()
    wiim_device.async_get_play_queue = AsyncMock(return_value=[])
    wiim_device.async_get_audio_output_modes = AsyncMock(return_value=[])
    wiim_device.async_get_input_modes = AsyncMock(return_value=[])
    wiim_device.async_get_play_mediums = AsyncMock(return_value=[])
    wiim_device.sync_device_duration_and_position = AsyncMock()

    return wiim_device


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
def mock_hass_for_media_player(mock_hass: HomeAssistant) -> HomeAssistant:
    """Fixture for HomeAssistant mock specifically for media player tests."""
    mock_hass.data[DOMAIN] = dr.DeviceRegistry(mock_hass)
    return mock_hass


@pytest.fixture
def mock_wiim_controller():
    """Mock a WiimController instance."""
    controller = MagicMock()
    controller.disconnect = AsyncMock()
    return controller


@pytest.fixture
def mock_wiim_media_player_entity(
    mock_wiim_device: WiimDevice, mock_config_entry: ConfigEntry
) -> WiimMediaPlayerEntity:
    """Fixture for a WiimMediaPlayerEntity instance."""
    entity = WiimMediaPlayerEntity(mock_wiim_device, mock_config_entry)
    entity._attr_unique_id = f"{mock_wiim_device.udn}-media_player"
    return entity


@pytest.fixture
def mock_http_api():
    """Mock WiimApiEndpoint."""
    api = AsyncMock()
    api.json_request = AsyncMock(return_value={"status": "ok"})
    return api
