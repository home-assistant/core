"""Test the Motion Blinds config flow."""
import socket

import pytest

from homeassistant import config_entries
from homeassistant.components.motion_blinds.config_flow import DEFAULT_GATEWAY_NAME
from homeassistant.components.motion_blinds.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST

from tests.async_mock import Mock, patch

TEST_HOST = "1.2.3.4"
TEST_API_KEY = "12ab345c-d67e-8f"
TEST_DEVICE_LIST = {"mac": Mock()}


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
        {CONF_HOST: TEST_HOST, CONF_API_KEY: TEST_API_KEY},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_GATEWAY_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
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

    with patch(
        "homeassistant.components.motion_blinds.gateway.MotionGateway.GetDeviceList",
        side_effect=socket.timeout,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: TEST_HOST, CONF_API_KEY: TEST_API_KEY},
        )

    assert result["type"] == "abort"
    assert result["reason"] == "connection_error"
