"""Tests for ActronAir OAuth2 Device Code Flow."""

from unittest.mock import patch

import pytest

from homeassistant.components.actronair.config_flow import ActronAirOAuth2FlowHandler
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_device_code_response():
    """Mock response of fetching device code."""
    return {
        "device_code": "test-device-code",
        "user_code": "123-456",
        "verification_uri": "https://example.com/activate",
        "verification_uri_complete": "https://example.com/activate?user_code=123-456",
        "interval": 5,
        "expires_in": 600,
    }


@pytest.fixture
def mock_token_response():
    """Mock token fetching response."""
    return {
        "access_token": "test-access-token",
        "refresh_token": "test-refresh-token",
        "expires_in": 3600,
    }


@pytest.fixture
def mock_user_info():
    """Mock User Info."""
    return {"id": "user123", "email": "user@example.com"}


async def test_user_step_successful_flow(
    hass: HomeAssistant,
    mock_device_code_response,
    mock_token_response,
    mock_user_info,
) -> None:
    """Test a full successful config flow."""

    flow = ActronAirOAuth2FlowHandler()
    flow.hass = hass

    with (
        patch.object(
            flow, "request_device_code", return_value=mock_device_code_response
        ),
        patch.object(flow, "async_check_auth", return_value=mock_token_response),
        patch.object(flow, "async_get_user_info", return_value=mock_user_info),
        patch.object(flow, "_abort_if_unique_id_configured", return_value=None),
    ):
        # Simulate user visiting the config flow
        result = await flow.async_step_user(user_input={})
        assert result["type"] == "create_entry"
        assert result["title"] == "ActronAir"
        assert "token" in result["data"]


async def test_user_step_device_code_failure(hass: HomeAssistant) -> None:
    """Test when the device code request fails."""

    flow = ActronAirOAuth2FlowHandler()
    flow.hass = hass

    with patch.object(flow, "request_device_code", return_value=None):
        result = await flow.async_step_user()
        assert result["type"] == "abort"
        assert result["reason"] == "device_code_request_failed"
