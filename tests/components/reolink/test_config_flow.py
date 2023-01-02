"""Test the Reolink config flow."""
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from reolink_ip.exceptions import ApiError, CredentialsInvalidError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.reolink import const
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
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


def get_mock_info(error=None, host_data_return=True):
    """Return a mock gateway info instance."""
    host_mock = Mock()
    if error is None:
        host_mock.get_host_data = AsyncMock(return_value=host_data_return)
    else:
        host_mock.get_host_data = AsyncMock(side_effect=error)
    host_mock.unsubscribe_all = AsyncMock(return_value=True)
    host_mock.logout = AsyncMock(return_value=True)
    host_mock.mac_address = TEST_MAC
    host_mock.onvif_enabled = True
    host_mock.rtmp_enabled = True
    host_mock.rtsp_enabled = True
    host_mock.nvr_name = TEST_NVR_NAME
    host_mock.port = TEST_PORT
    host_mock.use_https = TEST_USE_HTTPS
    return host_mock


@pytest.fixture(name="reolink_connect", autouse=True)
def reolink_connect_fixture(mock_get_source_ip):
    """Mock reolink connection and entry setup."""
    with patch(
        "homeassistant.components.reolink.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.reolink.host.Host", return_value=get_mock_info()
    ):
        yield


async def test_config_flow_manual_success(hass):
    """Successful flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NVR_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: TEST_PORT,
        const.CONF_USE_HTTPS: TEST_USE_HTTPS,
    }
    assert result["options"] == {
        const.CONF_PROTOCOL: const.DEFAULT_PROTOCOL,
    }


async def test_config_flow_errors(hass):
    """Successful flow manually initialized by the user after some errors."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    host_mock = get_mock_info(host_data_return=False)
    with patch("homeassistant.components.reolink.host.Host", return_value=host_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_HOST: TEST_HOST,
            },
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"host": "cannot_connect"}

    host_mock = get_mock_info(error=json.JSONDecodeError("test_error", "test", 1))
    with patch("homeassistant.components.reolink.host.Host", return_value=host_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_HOST: TEST_HOST,
            },
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"host": "unknown"}

    host_mock = get_mock_info(error=CredentialsInvalidError("Test error"))
    with patch("homeassistant.components.reolink.host.Host", return_value=host_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_HOST: TEST_HOST,
            },
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"host": "invalid_auth"}

    host_mock = get_mock_info(error=ApiError("Test error"))
    with patch("homeassistant.components.reolink.host.Host", return_value=host_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_HOST: TEST_HOST,
            },
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"host": "api_error"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            const.CONF_USE_HTTPS: TEST_USE_HTTPS,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NVR_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: TEST_PORT,
        const.CONF_USE_HTTPS: TEST_USE_HTTPS,
    }
    assert result["options"] == {
        const.CONF_PROTOCOL: const.DEFAULT_PROTOCOL,
    }


async def test_options_flow(hass):
    """Test specifying non default settings using options flow."""
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
            const.CONF_PROTOCOL: "rtsp",
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={const.CONF_PROTOCOL: "rtmp"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        const.CONF_PROTOCOL: "rtmp",
    }


async def test_change_connection_settings(hass):
    """Test changing connection settings by issuing a second user config flow."""
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
            const.CONF_PROTOCOL: const.DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST2,
            CONF_USERNAME: TEST_USERNAME2,
            CONF_PASSWORD: TEST_PASSWORD2,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == TEST_HOST2
    assert config_entry.data[CONF_USERNAME] == TEST_USERNAME2
    assert config_entry.data[CONF_PASSWORD] == TEST_PASSWORD2
