"""Test the config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.daybetter_services.config_flow import ConfigFlow
from homeassistant.data_entry_flow import FlowResultType

from .const import CONF_USER_CODE


@pytest.fixture
def config_flow() -> ConfigFlow:
    """Create a config flow instance."""
    return ConfigFlow()


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = AsyncMock()
    hass.config_entries = AsyncMock()
    return hass


class TestConfigFlow:
    """Test the config flow."""

    @pytest.mark.asyncio
    async def test_user_step_success(self, config_flow, mock_hass):
        """Test successful user step."""
        config_flow.hass = mock_hass

        with patch(
            "homeassistant.components.daybetter_services.config_flow.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock successful API response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={"code": 1, "data": {"hassCodeToken": "test_token_12345"}}
            )
            mock_session.post.return_value = mock_response

            result = await config_flow.async_step_user(
                {CONF_USER_CODE: "test_user_code"}
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["title"] == "DayBetter Services"
            assert result["data"][CONF_USER_CODE] == "test_user_code"
            assert result["data"]["token"] == "test_token_12345"

    @pytest.mark.asyncio
    async def test_user_step_auth_failed(self, config_flow, mock_hass):
        """Test user step with authentication failure."""
        config_flow.hass = mock_hass

        with patch(
            "homeassistant.components.daybetter_services.config_flow.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock failed API response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={"code": 0, "message": "Invalid user code"}
            )
            mock_session.post.return_value = mock_response

            result = await config_flow.async_step_user({CONF_USER_CODE: "invalid_code"})

            assert result["type"] == FlowResultType.FORM
            assert result["errors"]["base"] == "auth_failed"

    @pytest.mark.asyncio
    async def test_user_step_connection_error(self, config_flow, mock_hass):
        """Test user step with connection error."""
        config_flow.hass = mock_hass

        with patch(
            "homeassistant.components.daybetter_services.config_flow.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock connection error
            mock_session.post.side_effect = Exception("Connection failed")

            result = await config_flow.async_step_user(
                {CONF_USER_CODE: "test_user_code"}
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"]["base"] == "connection_error"

    @pytest.mark.asyncio
    async def test_user_step_http_error(self, config_flow, mock_hass):
        """Test user step with HTTP error."""
        config_flow.hass = mock_hass

        with patch(
            "homeassistant.components.daybetter_services.config_flow.async_get_clientsession"
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session

            # Mock HTTP error response
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_session.post.return_value = mock_response

            result = await config_flow.async_step_user(
                {CONF_USER_CODE: "test_user_code"}
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"]["base"] == "auth_failed"

    @pytest.mark.asyncio
    async def test_user_step_no_input(self, config_flow, mock_hass):
        """Test user step with no input."""
        config_flow.hass = mock_hass

        result = await config_flow.async_step_user(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
