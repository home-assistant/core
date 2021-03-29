"""Tests for iAqualink config flow."""
from unittest.mock import patch

import iaqualink.exception
import pytest

from homeassistant.components.iaqualink import DOMAIN, config_flow

from . import MOCK_CONFIG_DATA

from tests.common import MockConfigEntry, mock_coro


@pytest.mark.parametrize("step", ["import", "user"])
async def test_already_configured(hass, step):
    """Test config flow when iaqualink component is already setup."""
    MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA).add_to_hass(hass)

    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    fname = f"async_step_{step}"
    func = getattr(flow, fname)
    result = await func(MOCK_CONFIG_DATA)

    assert result["type"] == "abort"


@pytest.mark.parametrize("step", ["import", "user"])
async def test_without_config(hass, step):
    """Test with no configuration."""
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
async def test_with_invalid_credentials(hass, step):
    """Test config flow with invalid username and/or password."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass

    fname = f"async_step_{step}"
    func = getattr(flow, fname)
    with patch(
        "iaqualink.client.AqualinkClient.login",
        side_effect=iaqualink.exception.AqualinkServiceUnauthorizedException,
    ):
        result = await func(MOCK_CONFIG_DATA)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize("step", ["import", "user"])
async def test_service_exception(hass, step):
    """Test config flow encountering service exception."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass

    fname = f"async_step_{step}"
    func = getattr(flow, fname)
    with patch(
        "iaqualink.client.AqualinkClient.login",
        side_effect=iaqualink.exception.AqualinkServiceException,
    ):
        result = await func(MOCK_CONFIG_DATA)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize("step", ["import", "user"])
async def test_with_existing_config(hass, step):
    """Test with existing configuration."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    fname = f"async_step_{step}"
    func = getattr(flow, fname)
    with patch("iaqualink.client.AqualinkClient.login", return_value=mock_coro(None)):
        result = await func(MOCK_CONFIG_DATA)

    assert result["type"] == "create_entry"
    assert result["title"] == MOCK_CONFIG_DATA["username"]
    assert result["data"] == MOCK_CONFIG_DATA
