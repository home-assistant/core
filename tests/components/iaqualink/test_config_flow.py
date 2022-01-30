"""Tests for iAqualink config flow."""
from unittest.mock import patch

from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)
import pytest

from homeassistant.components.iaqualink import config_flow


@pytest.mark.parametrize("step", ["import", "user"])
async def test_already_configured(hass, config_entry, config_data, step):
    """Test config flow when iaqualink component is already setup."""
    config_entry.add_to_hass(hass)

    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    fname = f"async_step_{step}"
    func = getattr(flow, fname)
    result = await func(config_data)

    assert result["type"] == "abort"


@pytest.mark.parametrize("step", ["import", "user"])
async def test_without_config(hass, step):
    """Test config flow with no configuration."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    fname = f"async_step_{step}"
    func = getattr(flow, fname)
    result = await func()

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


@pytest.mark.parametrize("step", ["import", "user"])
async def test_with_invalid_credentials(hass, config_data, step):
    """Test config flow with invalid username and/or password."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass

    fname = f"async_step_{step}"
    func = getattr(flow, fname)
    with patch(
        "homeassistant.components.iaqualink.config_flow.AqualinkClient.login",
        side_effect=AqualinkServiceUnauthorizedException,
    ):
        result = await func(config_data)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize("step", ["import", "user"])
async def test_service_exception(hass, config_data, step):
    """Test config flow encountering service exception."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass

    fname = f"async_step_{step}"
    func = getattr(flow, fname)
    with patch(
        "homeassistant.components.iaqualink.config_flow.AqualinkClient.login",
        side_effect=AqualinkServiceException,
    ):
        result = await func(config_data)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize("step", ["import", "user"])
async def test_with_existing_config(hass, config_data, step):
    """Test config flow with existing configuration."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    fname = f"async_step_{step}"
    func = getattr(flow, fname)
    with patch(
        "homeassistant.components.iaqualink.config_flow.AqualinkClient.login",
        return_value=None,
    ):
        result = await func(config_data)

    assert result["type"] == "create_entry"
    assert result["title"] == config_data["username"]
    assert result["data"] == config_data
