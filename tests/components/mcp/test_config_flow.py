"""Test the Model Context Protocol config flow."""

from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from homeassistant import config_entries
from homeassistant.components.mcp.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_API_NAME

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_mcp_client: Mock
) -> None:
    """Test the complete configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "http://1.1.1.1/sse",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_API_NAME
    assert result["data"] == {
        CONF_URL: "http://1.1.1.1/sse",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (httpx.TimeoutException("Some timeout"), "timeout_connect"),
        (
            httpx.HTTPStatusError("", request=None, response=httpx.Response(500)),
            "cannot_connect",
        ),
        (httpx.HTTPError("Some HTTP error"), "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_mcp_client_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test we handle different client library errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "http://1.1.1.1/sse",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Reset the error and make sure the config flow can resume successfully.
    mock_mcp_client.side_effect = None
    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "http://1.1.1.1/sse",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_API_NAME
    assert result["data"] == {
        CONF_URL: "http://1.1.1.1/sse",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (
            httpx.HTTPStatusError("", request=None, response=httpx.Response(401)),
            "invalid_auth",
        ),
    ],
)
async def test_form_mcp_client_error_abort(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test we handle different client library errors that end with an abort."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "http://1.1.1.1/sse",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_error


@pytest.mark.parametrize(
    "user_input",
    [
        ({CONF_URL: "not a url"}),
        ({CONF_URL: "rtsp://1.1.1.1"}),
    ],
)
async def test_input_form_validation_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    user_input: dict[str, Any],
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_URL: "invalid_url"}

    # Reset the error and make sure the config flow can resume successfully.
    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "http://1.1.1.1/sse",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_API_NAME
    assert result["data"] == {
        CONF_URL: "http://1.1.1.1/sse",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_unique_url(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_mcp_client: Mock
) -> None:
    """Test that the same url cannot be configured twice."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://1.1.1.1/sse"},
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "http://1.1.1.1/sse",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_server_missing_capbilities(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
) -> None:
    """Test we handle different client library errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    response.capabilities.tools = None
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "http://1.1.1.1/sse",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_capabilities"
