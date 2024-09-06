"""Tests for Fing config flow."""

from unittest.mock import patch

import httpx

from homeassistant import config_entries
from homeassistant.components.fing.const import AGENT_IP, AGENT_KEY, AGENT_PORT, DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow_initialization(hass: HomeAssistant) -> None:
    """Test that the user config flow initializes correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_verify_connection_success(
    hass: HomeAssistant, mocked_entry, mocked_fing_agent_new_api
) -> None:
    """Test successful connection verification."""
    with patch(
        "homeassistant.components.fing.config_flow.FingAgent",
        return_value=mocked_fing_agent_new_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=mocked_entry
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            AGENT_IP: "192.168.1.1",
            AGENT_PORT: "49090",
            AGENT_KEY: "test_key",
            CONF_NAME: "Fing Agent",
        }


async def test_verify_api_version_outdated(
    hass: HomeAssistant, mocked_entry, mocked_fing_agent_old_api
) -> None:
    """Test connection verification failure."""
    with patch(
        "homeassistant.components.fing.config_flow.FingAgent",
        return_value=mocked_fing_agent_old_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=mocked_entry
        )

        assert result["type"] == FlowResultType.FORM
        assert (
            result["errors"]["base"]
            == "Network ID parameter is empty. Use the latest API."
        )


async def test_http_error_handling(hass: HomeAssistant, mocked_entry) -> None:
    """Test handling of HTTP-related errors during connection verification."""
    with patch(
        "homeassistant.components.fing.config_flow.FingAgent.get_devices",
        side_effect=httpx.HTTPError("HTTP error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=mocked_entry
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "HTTP exception -> Args: ('HTTP error',)"


async def test_invalid_url_handling(hass: HomeAssistant, mocked_entry) -> None:
    """Test handling of Invalid URL error."""
    with patch(
        "homeassistant.components.fing.config_flow.FingAgent.get_devices",
        side_effect=httpx.InvalidURL("Invalid URL"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=mocked_entry
        )

        assert result["type"] == FlowResultType.FORM
        assert (
            result["errors"]["base"]
            == "Invalid URL exception -> Args: ('Invalid URL',)"
        )


async def test_generic_error_handling(hass: HomeAssistant, mocked_entry) -> None:
    """Test handling of generic exceptions during connection verification."""
    with patch(
        "homeassistant.components.fing.config_flow.FingAgent.get_devices",
        side_effect=Exception("Generic error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=mocked_entry
        )

        assert result["type"] == FlowResultType.FORM
        assert (
            result["errors"]["base"]
            == "Generic exception raised -> Args: ('Generic error',)"
        )
