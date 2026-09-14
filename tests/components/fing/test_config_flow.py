"""Tests for Fing config flow."""

import httpx
import pytest

from homeassistant.components.fing.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import AsyncMock
from tests.conftest import MockConfigEntry


async def test_verify_connection_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_fing_agent: AsyncMock,
) -> None:
    """Test successful connection verification."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IP_ADDRESS: "192.168.1.1",
            CONF_PORT: "49090",
            CONF_API_KEY: "test_key",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == dict(mock_config_entry.data)

    entry = result["result"]
    assert entry.unique_id == "0000000000XX"
    assert entry.domain == DOMAIN


@pytest.mark.parametrize("api_type", ["old"])
async def test_verify_api_version_outdated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_fing_agent: AsyncMock,
) -> None:
    """Test connection verification failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IP_ADDRESS: "192.168.1.1",
            CONF_PORT: "49090",
            CONF_API_KEY: "test_key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "api_version_error"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (httpx.NetworkError("Network error"), "cannot_connect"),
        (httpx.TimeoutException("Timeout error"), "timeout_connect"),
        (
            httpx.HTTPStatusError(
                "HTTP status error - 500", request=None, response=httpx.Response(500)
            ),
            "http_status_error",
        ),
        (
            httpx.HTTPStatusError(
                "HTTP status error - 401", request=None, response=httpx.Response(401)
            ),
            "invalid_api_key",
        ),
        (httpx.HTTPError("HTTP error"), "unknown"),
        (httpx.InvalidURL("Invalid URL"), "url_error"),
        (httpx.CookieConflict("Cookie conflict"), "unknown"),
        (httpx.StreamError("Stream error"), "unknown"),
    ],
)
async def test_http_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_fing_agent: AsyncMock,
    error: str,
    exception: Exception,
) -> None:
    """Test handling of HTTP-related errors during connection verification."""
    mocked_fing_agent.get_devices.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IP_ADDRESS: "192.168.1.1",
            CONF_PORT: "49090",
            CONF_API_KEY: "test_key",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == error

    # Simulate a successful connection after the error
    mocked_fing_agent.get_devices.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IP_ADDRESS: "192.168.1.1",
            CONF_PORT: "49090",
            CONF_API_KEY: "test_key",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == dict(mock_config_entry.data)


async def test_duplicate_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_fing_agent: AsyncMock,
) -> None:
    """Test detecting duplicate entries."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IP_ADDRESS: "192.168.1.1",
            CONF_PORT: "49090",
            CONF_API_KEY: "test_key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
