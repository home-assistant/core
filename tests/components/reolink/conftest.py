"""Setup the Reolink tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from reolink_aio.api import Chime
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.reolink.config_flow import DEFAULT_PROTOCOL
from homeassistant.components.reolink.const import (
    CONF_BC_ONLY,
    CONF_BC_PORT,
    CONF_SUPPORTS_PRIVACY_MODE,
    CONF_USE_HTTPS,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_HOST2 = "4.5.6.7"
TEST_USERNAME = "admin"
TEST_USERNAME2 = "username"
TEST_PASSWORD = "password"
TEST_PASSWORD2 = "new_password"
TEST_MAC = "aa:bb:cc:dd:ee:ff"
TEST_MAC2 = "ff:ee:dd:cc:bb:aa"
TEST_MAC_CAM = "11:22:33:44:55:66"
DHCP_FORMATTED_MAC = "aabbccddeeff"
TEST_UID = "ABC1234567D89EFG"
TEST_UID_CAM = "DEF7654321D89GHT"
TEST_PORT = 1234
TEST_NVR_NAME = "test_reolink_name"
TEST_CAM_NAME = "test_reolink_cam"
TEST_NVR_NAME2 = "test2_reolink_name"
TEST_CAM_NAME = "test_reolink_cam"
TEST_USE_HTTPS = True
TEST_HOST_MODEL = "RLN8-410"
TEST_ITEM_NUMBER = "P000"
TEST_CAM_MODEL = "RLC-123"
TEST_DUO_MODEL = "Reolink Duo PoE"
TEST_PRIVACY = True
TEST_BC_PORT = 5678


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.reolink.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


def _init_host_mock(host_mock: MagicMock) -> None:
    host_mock.get_host_data = AsyncMock(return_value=None)
    host_mock.get_states = AsyncMock(return_value=None)
    host_mock.get_state = AsyncMock()
    host_mock.async_get_time = AsyncMock()
    host_mock.check_new_firmware = AsyncMock(return_value=False)
    host_mock.subscribe = AsyncMock()
    host_mock.unsubscribe = AsyncMock(return_value=True)
    host_mock.logout = AsyncMock(return_value=True)
    host_mock.reboot = AsyncMock()
    host_mock.set_ptz_command = AsyncMock()
    host_mock.get_motion_state_all_ch = AsyncMock(return_value=False)
    host_mock.get_stream_source = AsyncMock()
    host_mock.get_snapshot = AsyncMock()
    host_mock.get_encoding = AsyncMock(return_value="h264")
    host_mock.pull_point_request = AsyncMock()
    host_mock.set_audio = AsyncMock()
    host_mock.set_email = AsyncMock()
    host_mock.set_siren = AsyncMock()
    host_mock.ONVIF_event_callback = AsyncMock()
    host_mock.set_whiteled = AsyncMock()
    host_mock.set_state_light = AsyncMock()
    host_mock.renew = AsyncMock()
    host_mock.get_vod_source = AsyncMock()
    host_mock.request_vod_files = AsyncMock()
    host_mock.expire_session = AsyncMock()
    host_mock.set_volume = AsyncMock()
    host_mock.set_hub_audio = AsyncMock()
    host_mock.play_quick_reply = AsyncMock()
    host_mock.update_firmware = AsyncMock()
    host_mock.is_nvr = True
    host_mock.is_hub = False
    host_mock.mac_address = TEST_MAC
    host_mock.uid = TEST_UID
    host_mock.onvif_enabled = True
    host_mock.rtmp_enabled = True
    host_mock.rtsp_enabled = True
    host_mock.nvr_name = TEST_NVR_NAME
    host_mock.port = TEST_PORT
    host_mock.use_https = TEST_USE_HTTPS
    host_mock.is_admin = True
    host_mock.user_level = "admin"
    host_mock.protocol = "rtsp"
    host_mock.channels = [0]
    host_mock.stream_channels = [0]
    host_mock.new_devices = False
    host_mock.sw_version_update_required = False
    host_mock.hardware_version = "IPC_00000"
    host_mock.sw_version = "v1.0.0.0.0.0000"
    host_mock.sw_upload_progress.return_value = 100
    host_mock.manufacturer = "Reolink"
    host_mock.model = TEST_HOST_MODEL
    host_mock.supported.return_value = True
    host_mock.item_number.return_value = TEST_ITEM_NUMBER
    host_mock.camera_model.return_value = TEST_CAM_MODEL
    host_mock.camera_name.return_value = TEST_NVR_NAME
    host_mock.camera_hardware_version.return_value = "IPC_00001"
    host_mock.camera_sw_version.return_value = "v1.1.0.0.0.0000"
    host_mock.camera_sw_version_update_required.return_value = False
    host_mock.camera_uid.return_value = TEST_UID_CAM
    host_mock.camera_online.return_value = True
    host_mock.channel_for_uid.return_value = 0
    host_mock.firmware_update_available.return_value = False
    host_mock.session_active = True
    host_mock.timeout = 60
    host_mock.renewtimer.return_value = 600
    host_mock.wifi_connection = False
    host_mock.wifi_signal.return_value = -45
    host_mock.whiteled_mode_list.return_value = []
    host_mock.post_recording_time_list.return_value = []
    host_mock.zoom_range.return_value = {
        "zoom": {"pos": {"min": 0, "max": 100}},
        "focus": {"pos": {"min": 0, "max": 100}},
    }
    host_mock.capabilities = {"Host": ["RTSP"], "0": ["motion_detection"]}
    host_mock.checked_api_versions = {"GetEvents": 1}
    host_mock.abilities = {"abilityChn": [{"aiTrack": {"permit": 0, "ver": 0}}]}
    host_mock.get_raw_host_data.return_value = (
        "{'host':'TEST_RESPONSE','channel':'TEST_RESPONSE'}"
    )

    # enums
    host_mock.whiteled_mode.return_value = 1
    host_mock.whiteled_mode_list.return_value = ["off", "auto"]
    host_mock.doorbell_led.return_value = "Off"
    host_mock.doorbell_led_list.return_value = ["stayoff", "auto"]
    host_mock.auto_track_method.return_value = 3
    host_mock.daynight_state.return_value = "Black&White"
    host_mock.hub_alarm_tone_id.return_value = 1
    host_mock.hub_visitor_tone_id.return_value = 1
    host_mock.recording_packing_time_list = ["30 Minutes", "60 Minutes"]
    host_mock.recording_packing_time = "60 Minutes"

    # Baichuan
    host_mock.baichuan = MagicMock()
    host_mock.baichuan_only = False
    # Disable tcp push by default for tests
    host_mock.baichuan.port = TEST_BC_PORT
    host_mock.baichuan.events_active = False
    host_mock.baichuan.subscribe_events = AsyncMock()
    host_mock.baichuan.unsubscribe_events = AsyncMock()
    host_mock.baichuan.check_subscribe_events = AsyncMock()
    host_mock.baichuan.get_privacy_mode = AsyncMock()
    host_mock.baichuan.set_privacy_mode = AsyncMock()
    host_mock.baichuan.set_scene = AsyncMock()
    host_mock.baichuan.mac_address.return_value = TEST_MAC_CAM
    host_mock.baichuan.privacy_mode.return_value = False
    host_mock.baichuan.day_night_state.return_value = "day"
    host_mock.baichuan.subscribe_events.side_effect = ReolinkError("Test error")
    host_mock.baichuan.active_scene = "off"
    host_mock.baichuan.scene_names = ["off", "home"]
    host_mock.baichuan.abilities = {
        0: {"chnID": 0, "aitype": 34615},
        "Host": {"pushAlarm": 7},
    }
    host_mock.baichuan.set_smart_ai = AsyncMock()
    host_mock.baichuan.smart_location_list.return_value = [0]
    host_mock.baichuan.smart_ai_type_list.return_value = ["people"]
    host_mock.baichuan.smart_ai_index.return_value = 1
    host_mock.baichuan.smart_ai_name.return_value = "zone1"


@pytest.fixture
def reolink_host_class() -> Generator[MagicMock]:
    """Mock reolink connection and return both the host_mock and host_mock_class."""
    with patch(
        "homeassistant.components.reolink.host.Host", autospec=False
    ) as host_mock_class:
        _init_host_mock(host_mock_class.return_value)
        yield host_mock_class


@pytest.fixture
def reolink_host(reolink_host_class: MagicMock) -> Generator[MagicMock]:
    """Mock reolink Host class."""
    return reolink_host_class.return_value


@pytest.fixture
def reolink_platforms() -> Generator[None]:
    """Mock reolink entry setup."""
    with patch("homeassistant.components.reolink.PLATFORMS", return_value=[]):
        yield


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add the reolink mock config entry to hass."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            CONF_USE_HTTPS: TEST_USE_HTTPS,
            CONF_SUPPORTS_PRIVACY_MODE: TEST_PRIVACY,
            CONF_BC_PORT: TEST_BC_PORT,
            CONF_BC_ONLY: False,
        },
        options={
            CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def reolink_chime(reolink_host: MagicMock) -> None:
    """Mock a reolink chime."""
    TEST_CHIME = Chime(
        host=reolink_host,
        dev_id=12345678,
        channel=0,
    )
    TEST_CHIME.name = "Test chime"
    TEST_CHIME.volume = 3
    TEST_CHIME.connect_state = 2
    TEST_CHIME.led_state = True
    TEST_CHIME.event_info = {
        "md": {"switch": 0, "musicId": 0},
        "people": {"switch": 0, "musicId": 1},
        "visitor": {"switch": 1, "musicId": 2},
    }
    TEST_CHIME.remove = AsyncMock()
    TEST_CHIME.set_option = AsyncMock()

    reolink_host.chime_list = [TEST_CHIME]
    reolink_host.chime.return_value = TEST_CHIME
    return TEST_CHIME
