"""Tests for Fing config flow."""

from unittest.mock import patch

import httpx

from homeassistant.components.fing.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_verify_connection_success(
    hass: HomeAssistant, mocked_entry, mocked_fing_agent_new_api
) -> None:
    """Test successful connection verification."""
    with patch(
        "homeassistant.components.fing.config_flow.FingAgent",
        return_value=mocked_fing_agent_new_api,
    ):
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
    with patch(
        "homeassistant.components.fing.config_flow.FingAgent",
        return_value=mocked_fing_agent_old_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=mocked_entry
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "api_version_error"


async def test_http_error_handling(hass: HomeAssistant, mocked_entry) -> None:
    """Test handling of HTTP-related errors during connection verification."""
    with patch(
        "homeassistant.components.fing.config_flow.FingAgent.get_devices",
        side_effect=httpx.HTTPError("HTTP error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=mocked_entry
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "unexpected_error"


async def test_invalid_url_handling(hass: HomeAssistant, mocked_entry) -> None:
    """Test handling of Invalid URL error."""
    with patch(
        "homeassistant.components.fing.config_flow.FingAgent.get_devices",
        side_effect=httpx.InvalidURL("Invalid URL"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=mocked_entry
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "url_error"


async def test_generic_error_handling(hass: HomeAssistant, mocked_entry) -> None:
    """Test handling of generic exceptions during connection verification."""
    with patch(
        "homeassistant.components.fing.config_flow.FingAgent.get_devices",
        side_effect=Exception("Generic error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=mocked_entry
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "unexpected_error"
