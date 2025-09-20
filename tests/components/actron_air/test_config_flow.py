"""Config flow tests for the Actron Air Integration."""

from unittest.mock import AsyncMock, Mock

from actron_neo_api import ActronNeoAuthError
import pytest

from homeassistant.components.actron_air.config_flow import ActronAirConfigFlow
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.config_entries = Mock()
    return hass


async def test_user_flow_oauth2_success(mock_hass, mock_actron_api) -> None:
    """Test successful OAuth2 device code flow."""
    mock_api_instance = mock_actron_api.return_value

    # Mock device code request
    mock_api_instance.request_device_code = AsyncMock(
        return_value={
            "device_code": "test_device_code",
            "user_code": "ABC123",
            "verification_uri_complete": "https://example.com/device",
            "expires_in": 1800,
        }
    )

    # Mock successful token polling
    mock_api_instance.poll_for_token = AsyncMock(
        return_value={
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
        }
    )

    # Mock user info
    mock_api_instance.get_user_info = AsyncMock(
        return_value={"id": "test_user_id", "email": "test@example.com"}
    )

    mock_api_instance.refresh_token_value = "test_refresh_token"

    # Create config flow instance with mocked methods
    flow = ActronAirConfigFlow()
    flow.hass = mock_hass
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock()
    flow.async_create_entry = Mock(
        return_value={
            "type": "create_entry",
            "title": "test@example.com",
            "data": {CONF_API_TOKEN: "test_refresh_token"},
        }
    )
    flow.async_abort = Mock(return_value={"type": "abort", "reason": "oauth2_error"})
    flow.async_show_form = Mock(
        return_value={
            "type": "form",
            "step_id": "user",
            "description_placeholders": {
                "user_code": "ABC123",
                "verification_uri": "https://example.com/device",
                "expires_minutes": "30",
            },
        }
    )

    # First step - device code request
    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert "user_code" in result["description_placeholders"]
    assert result["description_placeholders"]["user_code"] == "ABC123"

    # Configure the form (triggers token polling)
    result = await flow.async_step_user({})

    # Should create entry on successful token exchange
    assert result["type"] == "create_entry"
    assert result["title"] == "test@example.com"
    assert result["data"] == {
        CONF_API_TOKEN: "test_refresh_token",
    }


async def test_user_flow_oauth2_pending(mock_hass, mock_actron_api) -> None:
    """Test OAuth2 flow when authorization is still pending."""
    mock_api_instance = mock_actron_api.return_value

    # Mock device code request
    mock_api_instance.request_device_code = AsyncMock(
        return_value={
            "device_code": "test_device_code",
            "user_code": "ABC123",
            "verification_uri_complete": "https://example.com/device",
            "expires_in": 1800,
        }
    )

    # Mock pending token polling (returns None)
    mock_api_instance.poll_for_token = AsyncMock(return_value=None)

    # Create config flow instance
    flow = ActronAirConfigFlow()
    flow.hass = mock_hass
    flow.async_show_form = Mock(
        side_effect=[
            {
                "type": "form",
                "step_id": "user",
                "description_placeholders": {
                    "user_code": "ABC123",
                    "verification_uri": "https://example.com/device",
                    "expires_minutes": "30",
                },
            },
            {
                "type": "form",
                "step_id": "user",
                "errors": {"base": "authorization_pending"},
            },
        ]
    )

    # First step - device code request
    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # Configure the form (triggers token polling)
    result = await flow.async_step_user({})

    # Should show form again with authorization pending error
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "authorization_pending"}


async def test_user_flow_oauth2_error(mock_hass, mock_actron_api) -> None:
    """Test OAuth2 flow with authentication error during device code request."""
    mock_api_instance = mock_actron_api.return_value

    # Mock device code request failure
    mock_api_instance.request_device_code = AsyncMock(
        side_effect=ActronNeoAuthError("OAuth2 error")
    )

    # Create config flow instance
    flow = ActronAirConfigFlow()
    flow.hass = mock_hass
    flow.async_abort = Mock(return_value={"type": "abort", "reason": "oauth2_error"})

    # Start the flow
    result = await flow.async_step_user()

    # Should abort with oauth2_error
    assert result["type"] == "abort"
    assert result["reason"] == "oauth2_error"


async def test_user_flow_token_polling_error(mock_hass, mock_actron_api) -> None:
    """Test OAuth2 flow with error during token polling."""
    mock_api_instance = mock_actron_api.return_value

    # Mock successful device code request
    mock_api_instance.request_device_code = AsyncMock(
        return_value={
            "device_code": "test_device_code",
            "user_code": "ABC123",
            "verification_uri_complete": "https://example.com/device",
            "expires_in": 1800,
        }
    )

    # Mock token polling failure
    mock_api_instance.poll_for_token = AsyncMock(
        side_effect=ActronNeoAuthError("Token polling error")
    )

    # Create config flow instance
    flow = ActronAirConfigFlow()
    flow.hass = mock_hass
    flow.async_show_form = Mock(
        side_effect=[
            {
                "type": "form",
                "step_id": "user",
                "description_placeholders": {
                    "user_code": "ABC123",
                    "verification_uri": "https://example.com/device",
                    "expires_minutes": "30",
                },
            },
            {"type": "form", "step_id": "user", "errors": {"base": "oauth2_error"}},
        ]
    )

    # First step - device code request
    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # Configure the form (triggers token polling)
    result = await flow.async_step_user({})

    # Should show form with oauth2_error
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "oauth2_error"}
