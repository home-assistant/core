"""Tests for the Ambiclimate config flow."""

from unittest.mock import AsyncMock, patch

import ambiclimate
import pytest

from homeassistant import config_entries
from homeassistant.components.ambiclimate import config_flow
from homeassistant.components.http import KEY_HASS
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResultType
from homeassistant.setup import async_setup_component
from homeassistant.util import aiohttp

from tests.common import MockConfigEntry


async def init_config_flow(hass):
    """Init a configuration flow."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    await async_setup_component(hass, "http", {})

    config_flow.register_flow_implementation(hass, "id", "secret")
    flow = config_flow.AmbiclimateFlowHandler()

    flow.hass = hass
    return flow


async def test_abort_if_no_implementation_registered(hass: HomeAssistant) -> None:
    """Test we abort if no implementation is registered."""
    flow = config_flow.AmbiclimateFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_configuration"


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if Ambiclimate is already setup."""
    flow = await init_config_flow(hass)

    MockConfigEntry(domain=config_flow.DOMAIN).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    with pytest.raises(AbortFlow):
        result = await flow.async_step_code()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_full_flow_implementation(hass: HomeAssistant) -> None:
    """Test registering an implementation and finishing flow works."""
    config_flow.register_flow_implementation(hass, None, None)
    flow = await init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert (
        result["description_placeholders"]["cb_url"]
        == "https://example.com/api/ambiclimate"
    )

    url = result["description_placeholders"]["authorization_url"]
    assert "https://api.ambiclimate.com/oauth2/authorize" in url
    assert "client_id=id" in url
    assert "response_type=code" in url
    assert "redirect_uri=https%3A%2F%2Fexample.com%2Fapi%2Fambiclimate" in url

    with patch("ambiclimate.AmbiclimateOAuth.get_access_token", return_value="test"):
        result = await flow.async_step_code("123ABC")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ambiclimate"
    assert result["data"]["callback_url"] == "https://example.com/api/ambiclimate"
    assert result["data"][CONF_CLIENT_SECRET] == "secret"
    assert result["data"][CONF_CLIENT_ID] == "id"

    with patch("ambiclimate.AmbiclimateOAuth.get_access_token", return_value=None):
        result = await flow.async_step_code("123ABC")
    assert result["type"] is FlowResultType.ABORT

    with patch(
        "ambiclimate.AmbiclimateOAuth.get_access_token",
        side_effect=ambiclimate.AmbiclimateOauthError(),
    ):
        result = await flow.async_step_code("123ABC")
    assert result["type"] is FlowResultType.ABORT


async def test_abort_invalid_code(hass: HomeAssistant) -> None:
    """Test if no code is given to step_code."""
    config_flow.register_flow_implementation(hass, None, None)
    flow = await init_config_flow(hass)

    with patch("ambiclimate.AmbiclimateOAuth.get_access_token", return_value=None):
        result = await flow.async_step_code("invalid")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "access_token"


async def test_already_setup(hass: HomeAssistant) -> None:
    """Test when already setup."""
    MockConfigEntry(domain=config_flow.DOMAIN).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_view(hass: HomeAssistant) -> None:
    """Test view."""
    hass.config_entries.flow.async_init = AsyncMock()

    request = aiohttp.MockRequest(
        b"", query_string="code=test_code", mock_source="test"
    )
    request.app = {KEY_HASS: hass}
    view = config_flow.AmbiclimateAuthCallbackView()
    assert await view.get(request) == "OK!"

    request = aiohttp.MockRequest(b"", query_string="", mock_source="test")
    request.app = {KEY_HASS: hass}
    view = config_flow.AmbiclimateAuthCallbackView()
    assert await view.get(request) == "No code"
