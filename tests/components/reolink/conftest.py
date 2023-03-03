"""Test the Reolink config flow."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

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


def get_mock_info(error=None, user_level="admin", sw_required=False):
    """Return a mock gateway info instance."""
    host_mock = Mock()
    if error is None:
        host_mock.get_host_data = AsyncMock(return_value=None)
    else:
        host_mock.get_host_data = AsyncMock(side_effect=error)
    host_mock.check_new_firmware = AsyncMock(return_value=False)
    host_mock.unsubscribe = AsyncMock(return_value=True)
    host_mock.logout = AsyncMock(return_value=True)
    host_mock.mac_address = TEST_MAC
    host_mock.onvif_enabled = True
    host_mock.rtmp_enabled = True
    host_mock.rtsp_enabled = True
    host_mock.nvr_name = TEST_NVR_NAME
    host_mock.port = TEST_PORT
    host_mock.use_https = TEST_USE_HTTPS
    host_mock.is_admin = user_level == "admin"
    host_mock.user_level = user_level
    host_mock.sw_version_update_required = sw_required
    host_mock.timeout = 60
    host_mock.renewtimer = 600
    host_mock.get_states = AsyncMock(return_value=None)
    return host_mock


@pytest.fixture(name="reolink_connect", autouse=True)
def reolink_connect_fixture(mock_get_source_ip):
    """Mock reolink connection and entry setup."""
    with patch(
        "homeassistant.components.reolink.host.webhook.async_register",
        return_value=True,
    ), patch("homeassistant.components.reolink.PLATFORMS", return_value=[]), patch(
        "homeassistant.components.reolink.host.Host", return_value=get_mock_info()
    ):
        yield
