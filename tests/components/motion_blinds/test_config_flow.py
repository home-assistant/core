"""Test the Motion Blinds config flow."""
import socket

import pytest

from homeassistant import config_entries
from homeassistant.components.motion_blinds.config_flow import DEFAULT_GATEWAY_NAME
from homeassistant.components.motion_blinds.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST

from tests.async_mock import Mock, patch

TEST_HOST = "1.2.3.4"
TEST_HOST2 = "5.6.7.8"
TEST_API_KEY = "12ab345c-d67e-8f"
TEST_MAC = "ab:cd:ef:gh"
TEST_MAC2 = "ij:kl:mn:op"
TEST_DEVICE_LIST = {TEST_MAC: Mock()}

TEST_DISCOVERY_1 = {
    TEST_HOST: {
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

TEST_DISCOVERY_2 = {
    TEST_HOST: {
        "msgType": "GetDeviceListAck",
        "mac": TEST_MAC,
        "deviceType": "02000002",
        "ProtocolVersion": "0.9",
        "token": "12345A678B9CDEFG",
        "data": [
            {"mac": "abcdefghujkl", "deviceType": "02000002"},
            {"mac": "abcdefghujkl0001", "deviceType": "10000000"},
        ],
    },
    TEST_HOST2: {
        "msgType": "GetDeviceListAck",
        "mac": TEST_MAC2,
        "deviceType": "02000002",
        "ProtocolVersion": "0.9",
        "token": "12345A678B9CDEFG",
        "data": [
            {"mac": "abcdefghujkl", "deviceType": "02000002"},
            {"mac": "abcdefghujkl0001", "deviceType": "10000000"},
        ],
    },
}


@pytest.fixture(name="motion_blinds_connect", autouse=True)
def motion_blinds_connect_fixture():
    """Mock motion blinds connection and entry setup."""
    with patch(
        "homeassistant.components.motion_blinds.gateway.MotionGateway.GetDeviceList",
        return_value=True,
    ), patch(
        "homeassistant.components.motion_blinds.gateway.MotionGateway.Update",
        return_value=True,
    ), patch(
        "homeassistant.components.motion_blinds.gateway.MotionGateway.device_list",
        TEST_DEVICE_LIST,
    ), patch(
        "homeassistant.components.motion_blinds.config_flow.MotionDiscovery.discover",
        return_value=TEST_DISCOVERY_1,
    ), patch(
        "homeassistant.components.motion_blinds.async_setup_entry", return_value=True
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
        {CONF_HOST: TEST_HOST},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "connect"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: TEST_API_KEY},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_GATEWAY_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_API_KEY: TEST_API_KEY,
    }


async def test_config_flow_discovery_1_success(hass):
    """Successful flow with 1 gateway discovered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "connect"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: TEST_API_KEY},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_GATEWAY_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_API_KEY: TEST_API_KEY,
    }


async def test_config_flow_discovery_2_success(hass):
    """Successful flow with 2 gateway discovered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.motion_blinds.config_flow.MotionDiscovery.discover",
        return_value=TEST_DISCOVERY_2,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "select"
    assert result["data_schema"].schema["select_ip"].container == [
        TEST_HOST,
        TEST_HOST2,
    ]
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"select_ip": TEST_HOST2},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "connect"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: TEST_API_KEY},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_GATEWAY_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST2,
        CONF_API_KEY: TEST_API_KEY,
    }


async def test_config_flow_connection_error(hass):
    """Failed flow manually initialized by the user with connection timeout."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: TEST_HOST},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "connect"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.motion_blinds.gateway.MotionGateway.GetDeviceList",
        side_effect=socket.timeout,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: TEST_API_KEY},
        )

    assert result["type"] == "abort"
    assert result["reason"] == "connection_error"


async def test_config_flow_discovery_fail(hass):
    """Failed flow with no gateways discovered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.motion_blinds.config_flow.MotionDiscovery.discover",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "discovery_error"}
