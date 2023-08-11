"""Setup the Reolink tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.reolink import const
from homeassistant.components.reolink.config_flow import DEFAULT_PROTOCOL
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_HOST2 = "4.5.6.7"
TEST_USERNAME = "admin"
TEST_USERNAME2 = "username"
TEST_PASSWORD = "password"
TEST_PASSWORD2 = "new_password"
TEST_MAC = "ab:cd:ef:gh:ij:kl"
TEST_PORT = 1234
TEST_NVR_NAME = "test_reolink_name"
TEST_USE_HTTPS = True


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.reolink.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def reolink_connect(mock_get_source_ip: None) -> Generator[MagicMock, None, None]:
    """Mock reolink connection."""
    with patch(
        "homeassistant.components.reolink.host.webhook.async_register",
        return_value=True,
    ), patch(
        "homeassistant.components.reolink.host.Host", autospec=True
    ) as host_mock_class:
        host_mock = host_mock_class.return_value
        host_mock.get_host_data.return_value = None
        host_mock.get_states.return_value = None
        host_mock.check_new_firmware.return_value = False
        host_mock.unsubscribe.return_value = True
        host_mock.logout.return_value = True
        host_mock.mac_address = TEST_MAC
        host_mock.onvif_enabled = True
        host_mock.rtmp_enabled = True
        host_mock.rtsp_enabled = True
        host_mock.nvr_name = TEST_NVR_NAME
        host_mock.port = TEST_PORT
        host_mock.use_https = TEST_USE_HTTPS
        host_mock.is_admin = True
        host_mock.user_level = "admin"
        host_mock.sw_version_update_required = False
        host_mock.timeout = 60
        host_mock.renewtimer.return_value = 600
        yield host_mock


@pytest.fixture
def reolink_ONVIF_wait() -> Generator[None, None, None]:
    """Mock reolink connection."""
    with patch("homeassistant.components.reolink.host.asyncio.Event.wait", AsyncMock()):
        yield


@pytest.fixture
def reolink_platforms(mock_get_source_ip: None) -> Generator[None, None, None]:
    """Mock reolink entry setup."""
    with patch("homeassistant.components.reolink.PLATFORMS", return_value=[]):
        yield


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add the reolink mock config entry to hass."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            const.CONF_USE_HTTPS: TEST_USE_HTTPS,
        },
        options={
            const.CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)
    return config_entry
