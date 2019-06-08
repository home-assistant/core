"""Tests for iAqualink config flow."""
from unittest.mock import patch

import iaqualink

from homeassistant.components.iaqualink import config_flow

from tests.common import MockConfigEntry, mock_coro

DATA = {"username": "test@example.com", "password": "pass"}


async def test_already_configured(hass):
    """Test if a HomeKit discovered bridge has already been configured."""
    MockConfigEntry(domain="iaqualink", data=DATA).add_to_hass(hass)

    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_user(DATA)

    assert result["type"] == "abort"


async def test_import_with_invalid_credentials(hass):
    """Test config flow ."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass

    with patch(
        "iaqualink.AqualinkClient.login", side_effect=iaqualink.AqualinkLoginException
    ):
        result = await flow.async_step_user(DATA)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "connection_failure"}


async def test_import_with_existing_config(hass):
    """Test importing a host with an existing config file."""
    flow = config_flow.AqualinkFlowHandler()
    flow.hass = hass
    flow.context = {}

    with patch("iaqualink.AqualinkClient.login", return_value=mock_coro(None)):
        result = await flow.async_step_user(DATA)

    assert result["type"] == "create_entry"
    assert result["title"] == DATA["username"]
    assert result["data"] == DATA
