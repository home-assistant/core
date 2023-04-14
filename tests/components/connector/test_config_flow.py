"""Test the connector config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.connector.const import DEFAULT_HUB_NAME, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST

TEST_HOST = "192.168.31.100"
TEST_API_KEY = "12ab345c-d67e-8f"
TEST_MAC = "ab:cd:ef:gh"

TEST_DISCOVERY_1 = {
    "192.168.31.100": {
        "msgType": "GetDeviceListAck",
        "mac": TEST_MAC,
        "deviceType": "02000002",
        "ProtocolVersion": "0.9",
        "token": "12345A678B9CDEFG",
        "data": [
            {"mac": "abcdefghujkl", "deviceType": "02000002"},
            {"mac": "abcdefghujkl0001", "deviceType": "10000000"},
            {"mac": "abcdefghujkl0002", "deviceType": "10000000"},
        ],
    }
}


@pytest.fixture(name="connector_connect", autouse=True)
def connector_connect_fixture():
    """Mock connector connection and entry setup."""
    with patch(
        "homeassistant.components.connector.config_flow.ConnectorHub.device_list",
        return_value=TEST_DISCOVERY_1,
    ), patch(
        "homeassistant.components.connector.config_flow.ConnectorHub.start_receive_data",
        return_value=True,
    ), patch(
        "homeassistant.components.connector.config_flow.ConnectorHub.is_connected",
        True,
    ):
        yield


async def test_config_flow_manual_host_success(hass):
    """Successful flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: TEST_HOST, CONF_API_KEY: TEST_API_KEY},
    )
    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_HUB_NAME
    assert result["data"] == {
        CONF_HOST: [TEST_HOST],
        CONF_API_KEY: TEST_API_KEY,
    }


async def test_config_flow_manual_host_fail_device_error(hass):
    """Device not found by user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    with patch(
        "homeassistant.components.connector.config_flow.ConnectorHub.device_list",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_API_KEY: TEST_API_KEY},
        )
    assert result["type"] == "abort"
    assert result["reason"] == "device_none"


async def test_config_flow_manual_host_fail_key_error(hass):
    """The key entered by the user is wrong."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    with patch(
        "homeassistant.components.connector.config_flow.ConnectorHub.is_connected",
        False,
    ), patch(
        "homeassistant.components.connector.config_flow.ConnectorHub.error_code",
        1001,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_API_KEY: TEST_API_KEY},
        )
    assert result["type"] == "abort"
    assert result["reason"] == "key_error"


async def test_config_flow_manual_host_fail_port_error(hass):
    """Failed due to multicast port being occupied."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    with patch(
        "homeassistant.components.connector.config_flow.ConnectorHub.is_connected",
        False,
    ), patch(
        "homeassistant.components.connector.config_flow.ConnectorHub.error_code",
        1002,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_API_KEY: TEST_API_KEY},
        )
    assert result["type"] == "abort"
    assert result["reason"] == "port_error"
