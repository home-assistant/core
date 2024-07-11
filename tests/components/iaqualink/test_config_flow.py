"""Tests for iAqualink config flow."""

from unittest.mock import patch

from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)

from homeassistant.components.iaqualink import config_flow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_already_configured(
    hass: HomeAssistant, config_entry, config_data
) -> None:
    """Test config flow when iaqualink component is already setup."""
    config_entry.add_to_hass(hass)

    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_user(config_data)

    assert result["type"] is FlowResultType.ABORT


async def test_without_config(hass: HomeAssistant) -> None:
    """Test config flow with no configuration."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_user()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_with_invalid_credentials(hass: HomeAssistant, config_data) -> None:
    """Test config flow with invalid username and/or password."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.iaqualink.config_flow.AqualinkClient.login",
        side_effect=AqualinkServiceUnauthorizedException,
    ):
        result = await flow.async_step_user(config_data)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_service_exception(hass: HomeAssistant, config_data) -> None:
    """Test config flow encountering service exception."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.iaqualink.config_flow.AqualinkClient.login",
        side_effect=AqualinkServiceException,
    ):
        result = await flow.async_step_user(config_data)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_with_existing_config(hass: HomeAssistant, config_data) -> None:
    """Test config flow with existing configuration."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    with patch(
        "homeassistant.components.iaqualink.config_flow.AqualinkClient.login",
        return_value=None,
    ):
        result = await flow.async_step_user(config_data)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == config_data["username"]
    assert result["data"] == config_data
