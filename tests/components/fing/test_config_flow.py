"""Tests for Fing config flow."""

from fing_agent_api.models import DeviceResponse
import httpx
import pytest

from homeassistant.components.fing.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import load_json_object_fixture


async def test_verify_connection_success(
    hass: HomeAssistant, mocked_entry, mocked_fing_agent
) -> None:
    """Test successful connection verification."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=mocked_entry
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_IP_ADDRESS: "192.168.1.1",
        CONF_PORT: "49090",
        CONF_API_KEY: "test_key",
    }


async def test_verify_api_version_outdated(
    hass: HomeAssistant, mocked_entry, mocked_fing_agent_old_api
) -> None:
    """Test connection verification failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=mocked_entry
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "api_version_error"


@pytest.mark.parametrize(
    "error",
    [
        httpx.NetworkError("Network error"),
        httpx.TimeoutException("Timeout error"),
        httpx.HTTPStatusError(
            "HTTP status error - 500", request=None, response=httpx.Response(500)
        ),
        httpx.HTTPStatusError(
            "HTTP status error - 401", request=None, response=httpx.Response(401)
        ),
        httpx.HTTPError("HTTP error"),
        httpx.InvalidURL("Invalid URL"),
        httpx.CookieConflict("Cookie conflict"),
        httpx.StreamError("Stream error"),
        Exception("Generic error"),
    ],
)
async def test_http_error_handling(
    hass: HomeAssistant, mocked_entry, mocked_fing_agent, error
) -> None:
    """Test handling of HTTP-related errors during connection verification."""
    mocked_fing_agent.get_devices.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=mocked_entry
    )

    assert result["type"] is FlowResultType.FORM
    if isinstance(error, httpx.NetworkError):
        assert result["errors"]["base"] == "cannot_connect"
    elif isinstance(error, httpx.TimeoutException):
        assert result["errors"]["base"] == "timeout_connect"
    elif isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code == 401:
            assert result["errors"]["base"] == "invalid_api_key"
        else:
            assert result["errors"]["base"] == "http_status_error"
    elif isinstance(error, httpx.InvalidURL):
        assert result["errors"]["base"] == "url_error"
    elif isinstance(
        error, (httpx.CookieConflict, httpx.StreamError, httpx.HTTPError, Exception)
    ):
        assert result["errors"]["base"] == "unexpected_error"

    # Simulate a successful connection after the error
    mocked_fing_agent.get_devices.side_effect = None
    mocked_fing_agent.get_devices.return_value = DeviceResponse(
        load_json_object_fixture("device_resp_new_API.json", DOMAIN)
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=mocked_entry
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_IP_ADDRESS: "192.168.1.1",
        CONF_PORT: "49090",
        CONF_API_KEY: "test_key",
    }
