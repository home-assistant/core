"""Define tests for the Redgtech Waste config flow."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from homeassistant import data_entry_flow
from homeassistant.components.redgtech.config_flow import RedgtechConfigFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_ACCESS_TOKEN
from homeassistant.data_entry_flow import FlowResultType, AbortFlow
from redgtech_api.api import RedgtechAuthError, RedgtechConnectionError


@pytest.mark.asyncio
async def test_user_step_creates_entry():
    """Test if the configuration flow creates an entry correctly."""
    mock_hass = MagicMock()
    mock_hass.config_entries.async_entries = MagicMock(return_value=[])

    mock_flow = RedgtechConfigFlow()
    mock_flow.hass = mock_hass

    user_input = {
        CONF_EMAIL: "test@test.com",
        CONF_PASSWORD: "123456"
    }

    with patch("homeassistant.components.redgtech.config_flow.RedgtechAPI.login", return_value="fake_token"):
        result = await mock_flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == user_input[CONF_EMAIL]
    assert result["data"] == {
        CONF_EMAIL: "test@test.com",
        CONF_PASSWORD: "123456",
        CONF_ACCESS_TOKEN: "fake_token"
    }


@pytest.mark.asyncio
async def test_user_step_invalid_auth():
    """Test authentication failure with invalid credentials."""
    mock_hass = MagicMock()
    mock_hass.config_entries.async_entries = MagicMock(return_value=[])

    mock_flow = RedgtechConfigFlow()
    mock_flow.hass = mock_hass

    user_input = {
        CONF_EMAIL: "test@test.com",
        CONF_PASSWORD: "wrongpassword"
    }

    with patch("homeassistant.components.redgtech.config_flow.RedgtechAPI.login", side_effect=RedgtechAuthError):
        result = await mock_flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_user_step_cannot_connect():
    """Test connection failure to the API."""
    mock_hass = MagicMock()
    mock_hass.config_entries.async_entries = MagicMock(return_value=[])

    mock_flow = RedgtechConfigFlow()
    mock_flow.hass = mock_hass

    user_input = {
        CONF_EMAIL: "test@test.com",
        CONF_PASSWORD: "123456"
    }

    with patch("homeassistant.components.redgtech.config_flow.RedgtechAPI.login", side_effect=RedgtechConnectionError):
        result = await mock_flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_user_step_unknown_error():
    """Test unknown error during login."""
    mock_hass = MagicMock()
    mock_hass.config_entries.async_entries = MagicMock(return_value=[])

    mock_flow = RedgtechConfigFlow()
    mock_flow.hass = mock_hass

    user_input = {
        CONF_EMAIL: "test@test.com",
        CONF_PASSWORD: "123456"
    }

    with patch("homeassistant.components.redgtech.config_flow.RedgtechAPI.login", side_effect=Exception("generic error")):
        result = await mock_flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"
