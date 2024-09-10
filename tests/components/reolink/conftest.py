"""Setup the Reolink tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from reolink_aio.api import Chime

from homeassistant.components.reolink.config_flow import DEFAULT_PROTOCOL
from homeassistant.components.reolink.const import CONF_USE_HTTPS, DOMAIN
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


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.reolink.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def reolink_connect_class() -> Generator[MagicMock]:
    """Mock reolink connection and return both the host_mock and host_mock_class."""
    with (
        patch(
            "homeassistant.components.reolink.host.Host", autospec=True
        ) as host_mock_class,
    ):
        host_mock = host_mock_class.return_value
        host_mock.get_host_data.return_value = None
        host_mock.get_states.return_value = None
        host_mock.check_new_firmware.return_value = False
        host_mock.unsubscribe.return_value = True
        host_mock.logout.return_value = True
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
        host_mock.sw_version_update_required = False
        host_mock.hardware_version = "IPC_00000"
        host_mock.sw_version = "v1.0.0.0.0.0000"
        host_mock.manufacturer = "Reolink"
        host_mock.model = TEST_HOST_MODEL
        host_mock.item_number = TEST_ITEM_NUMBER
        host_mock.camera_model.return_value = TEST_CAM_MODEL
        host_mock.camera_name.return_value = TEST_NVR_NAME
        host_mock.camera_hardware_version.return_value = "IPC_00001"
        host_mock.camera_sw_version.return_value = "v1.1.0.0.0.0000"
        host_mock.camera_sw_version_update_required.return_value = False
        host_mock.camera_uid.return_value = TEST_UID_CAM
        host_mock.channel_for_uid.return_value = 0
        host_mock.get_encoding.return_value = "h264"
        host_mock.firmware_update_available.return_value = False
        host_mock.session_active = True
        host_mock.timeout = 60
        host_mock.renewtimer.return_value = 600
        host_mock.wifi_connection = False
        host_mock.wifi_signal = None
        host_mock.whiteled_mode_list.return_value = []
        host_mock.zoom_range.return_value = {
            "zoom": {"pos": {"min": 0, "max": 100}},
            "focus": {"pos": {"min": 0, "max": 100}},
        }
        host_mock.capabilities = {"Host": ["RTSP"], "0": ["motion_detection"]}
        host_mock.checked_api_versions = {"GetEvents": 1}
        host_mock.abilities = {"abilityChn": [{"aiTrack": {"permit": 0, "ver": 0}}]}

        # enums
        host_mock.whiteled_mode.return_value = 1
        host_mock.whiteled_mode_list.return_value = ["off", "auto"]
        host_mock.doorbell_led.return_value = "Off"
        host_mock.doorbell_led_list.return_value = ["stayoff", "auto"]
        host_mock.auto_track_method.return_value = 3
        host_mock.daynight_state.return_value = "Black&White"
        yield host_mock_class


@pytest.fixture
def reolink_connect(
    reolink_connect_class: MagicMock,
) -> Generator[MagicMock]:
    """Mock reolink connection."""
    return reolink_connect_class.return_value


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
        },
        options={
            CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def test_chime(reolink_connect: MagicMock) -> None:
    """Mock a reolink chime."""
    TEST_CHIME = Chime(
        host=reolink_connect,
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

    reolink_connect.chime_list = [TEST_CHIME]
    reolink_connect.chime.return_value = TEST_CHIME
    return TEST_CHIME
