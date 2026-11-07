"""Tests for Heiman Home config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from heimanconnect import HeimanAuthError, HeimanTokenExpiredError

from homeassistant.components.heiman_home.config_flow import HeimanConfigFlow
from homeassistant.components.heiman_home.const import CONF_USER_ID
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_config_flow_logger() -> None:
    """Test config flow logger property."""
    flow = HeimanConfigFlow()
    assert flow.logger.name == "homeassistant.components.heiman_home.config_flow"


async def test_config_flow_extra_authorize_data() -> None:
    """Test extra authorize data returns empty dict."""
    flow = HeimanConfigFlow()
    assert flow.extra_authorize_data == {}


async def test_oauth_create_entry_token_expired(hass: HomeAssistant) -> None:
    """Test OAuth entry creation with expired token."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(
        side_effect=HeimanTokenExpiredError("Token expired")
    )
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client.close = AsyncMock()
    mock_api_client.initialize = AsyncMock()

    with patch(
        "homeassistant.components.heiman_home.config_flow.HeimanApiClient",
        return_value=mock_api_client,
    ):
        result = await flow.async_oauth_create_entry(
            {CONF_TOKEN: {"access_token": "expired"}}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "token_expired"
    mock_api_client.close.assert_called_once()


async def test_oauth_create_entry_auth_error(hass: HomeAssistant) -> None:
    """Test OAuth entry creation with auth error."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(
        side_effect=HeimanAuthError("Auth failed")
    )
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client.close = AsyncMock()
    mock_api_client.initialize = AsyncMock()

    with patch(
        "homeassistant.components.heiman_home.config_flow.HeimanApiClient",
        return_value=mock_api_client,
    ):
        result = await flow.async_oauth_create_entry(
            {CONF_TOKEN: {"access_token": "invalid"}}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "token_invalid"
    mock_api_client.close.assert_called_once()


async def test_oauth_create_entry_user_info_exception(hass: HomeAssistant) -> None:
    """Test OAuth entry creation with user info exception."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(side_effect=Exception("Network error"))
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client.close = AsyncMock()
    mock_api_client.initialize = AsyncMock()

    with patch(
        "homeassistant.components.heiman_home.config_flow.HeimanApiClient",
        return_value=mock_api_client,
    ):
        result = await flow.async_oauth_create_entry(
            {CONF_TOKEN: {"access_token": "test"}}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "account_info_failed"
    mock_api_client.close.assert_called_once()


async def test_oauth_create_entry_no_homes(hass: HomeAssistant) -> None:
    """Test OAuth entry creation with no homes."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_user = MagicMock()
    mock_user.user_id = "test-user"

    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=mock_user)
    mock_wrapper.async_get_homes = AsyncMock(return_value=[])
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client.close = AsyncMock()
    mock_api_client.initialize = AsyncMock()

    with patch(
        "homeassistant.components.heiman_home.config_flow.HeimanApiClient",
        return_value=mock_api_client,
    ):
        result = await flow.async_oauth_create_entry(
            {CONF_TOKEN: {"access_token": "test"}}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_homes"
    mock_api_client.close.assert_called_once()


async def test_oauth_create_entry_homes_token_expired(hass: HomeAssistant) -> None:
    """Test OAuth entry creation with homes fetch token expired."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_user = MagicMock()
    mock_user.user_id = "test-user"

    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=mock_user)
    mock_wrapper.async_get_homes = AsyncMock(
        side_effect=HeimanTokenExpiredError("Token expired")
    )
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client.close = AsyncMock()
    mock_api_client.initialize = AsyncMock()

    with patch(
        "homeassistant.components.heiman_home.config_flow.HeimanApiClient",
        return_value=mock_api_client,
    ):
        result = await flow.async_oauth_create_entry(
            {CONF_TOKEN: {"access_token": "test"}}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "token_expired"
    mock_api_client.close.assert_called_once()


async def test_oauth_create_entry_homes_auth_error(hass: HomeAssistant) -> None:
    """Test OAuth entry creation with homes fetch auth error."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_user = MagicMock()
    mock_user.user_id = "test-user"

    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=mock_user)
    mock_wrapper.async_get_homes = AsyncMock(side_effect=HeimanAuthError("Auth failed"))
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client.close = AsyncMock()
    mock_api_client.initialize = AsyncMock()

    with patch(
        "homeassistant.components.heiman_home.config_flow.HeimanApiClient",
        return_value=mock_api_client,
    ):
        result = await flow.async_oauth_create_entry(
            {CONF_TOKEN: {"access_token": "test"}}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "token_invalid"
    mock_api_client.close.assert_called_once()


async def test_oauth_create_entry_homes_exception(hass: HomeAssistant) -> None:
    """Test OAuth entry creation with homes fetch exception."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_user = MagicMock()
    mock_user.user_id = "test-user"

    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=mock_user)
    mock_wrapper.async_get_homes = AsyncMock(side_effect=Exception("Network error"))
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client.close = AsyncMock()
    mock_api_client.initialize = AsyncMock()

    with patch(
        "homeassistant.components.heiman_home.config_flow.HeimanApiClient",
        return_value=mock_api_client,
    ):
        result = await flow.async_oauth_create_entry(
            {CONF_TOKEN: {"access_token": "test"}}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "account_info_failed"
    mock_api_client.close.assert_called_once()


async def test_oauth_create_entry_success(hass: HomeAssistant) -> None:
    """Test successful OAuth entry creation covers all homes on the account."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_user = MagicMock()
    mock_user.user_id = "test-user"
    mock_user.email = "test@example.com"
    mock_user.nickname = "John Doe"
    mock_user.get_display_name.return_value = "John Doe"

    mock_home1 = MagicMock()
    mock_home1.home_id = "home-1"
    mock_home2 = MagicMock()
    mock_home2.home_id = "home-2"

    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=mock_user)
    mock_wrapper.async_get_homes = AsyncMock(return_value=[mock_home1, mock_home2])
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client.close = AsyncMock()
    mock_api_client.initialize = AsyncMock()

    with (
        patch(
            "homeassistant.components.heiman_home.config_flow.HeimanApiClient",
            return_value=mock_api_client,
        ),
        patch.object(flow, "async_set_unique_id") as mock_set_unique,
        patch.object(flow, "_abort_if_unique_id_configured"),
    ):
        result = await flow.async_oauth_create_entry(
            {CONF_TOKEN: {"access_token": "test"}}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "John Doe"
    assert result["data"][CONF_USER_ID] == "test-user"
    assert CONF_TOKEN in result["data"]
    mock_set_unique.assert_called_once_with("test-user")
    mock_api_client.close.assert_called_once()
