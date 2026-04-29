"""Tests for Heiman Home config flow - comprehensive coverage."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from heimanconnect import HeimanAuthError, HeimanTokenExpiredError
import voluptuous as vol

from homeassistant.components.heiman_home.config_flow import AuthInfo, HeimanConfigFlow
from homeassistant.components.heiman_home.const import CONF_HOME_ID, CONF_USER_ID
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_auth_info_init() -> None:
    """Test AuthInfo initialization."""
    auth_info = AuthInfo()
    assert auth_info.homes == []
    assert auth_info.user_info is None
    assert auth_info.auth_data == {}


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


async def test_oauth_create_entry_success_single_home(hass: HomeAssistant) -> None:
    """Test successful OAuth entry creation with single home."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_user = MagicMock()
    mock_user.user_id = "test-user"
    mock_user.email = "test@example.com"
    mock_user.nickname = None

    mock_home = MagicMock()
    mock_home.home_id = "home-1"
    mock_home.home_name = "My Home"
    mock_home.device_count = 5

    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=mock_user)
    mock_wrapper.async_get_homes = AsyncMock(return_value=[mock_home])
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

        # Should proceed to select_home step
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_home"
        mock_api_client.close.assert_called_once()


async def test_select_home_no_selection(hass: HomeAssistant) -> None:
    """Test select_home step without user input."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_user = MagicMock()
    mock_user.user_id = "test-user"
    mock_user.email = "test@example.com"

    mock_home = MagicMock()
    mock_home.home_id = "home-1"
    mock_home.home_name = "My Home"
    mock_home.device_count = 5

    flow._auth_info.user_info = mock_user
    flow._auth_info.homes = [mock_home]
    flow._auth_info.auth_data = {CONF_TOKEN: {"access_token": "test"}}

    result = await flow.async_step_select_home()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_home"
    assert "user_email" in result["description_placeholders"]


async def test_select_home_no_home_id_selected(hass: HomeAssistant) -> None:
    """Test select_home with no home_id selected."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_user = MagicMock()
    mock_user.user_id = "test-user"
    mock_user.email = "test@example.com"

    mock_home = MagicMock()
    mock_home.home_id = "home-1"
    mock_home.home_name = "My Home"
    mock_home.device_count = 5

    flow._auth_info.user_info = mock_user
    flow._auth_info.homes = [mock_home]
    flow._auth_info.auth_data = {CONF_TOKEN: {"access_token": "test"}}

    result = await flow.async_step_select_home(user_input={CONF_HOME_ID: None})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_home"
    assert result["errors"] == {"base": "no_home_selected"}


async def test_select_home_empty_string_home_id(hass: HomeAssistant) -> None:
    """Test select_home with empty string home_id."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_user = MagicMock()
    mock_user.user_id = "test-user"
    mock_user.email = "test@example.com"

    mock_home = MagicMock()
    mock_home.home_id = "home-1"
    mock_home.home_name = "My Home"
    mock_home.device_count = 5

    flow._auth_info.user_info = mock_user
    flow._auth_info.homes = [mock_home]
    flow._auth_info.auth_data = {CONF_TOKEN: {"access_token": "test"}}

    result = await flow.async_step_select_home(user_input={CONF_HOME_ID: ""})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_home"
    assert result["errors"] == {"base": "no_home_selected"}


async def test_select_home_success_with_nickname(hass: HomeAssistant) -> None:
    """Test successful home selection with nickname."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_user = MagicMock()
    mock_user.user_id = "test-user"
    mock_user.email = "test@example.com"
    mock_user.nickname = "John Doe"
    mock_user.get_display_name.return_value = "John Doe"

    mock_home = MagicMock()
    mock_home.home_id = "home-1"
    mock_home.home_name = "My Home"
    mock_home.device_count = 5

    flow._auth_info.user_info = mock_user
    flow._auth_info.homes = [mock_home]
    flow._auth_info.auth_data = {CONF_TOKEN: {"access_token": "test"}}

    with (
        patch.object(flow, "async_set_unique_id") as mock_set_unique,
        patch.object(flow, "_abort_if_unique_id_configured"),
    ):
        result = await flow.async_step_select_home(user_input={CONF_HOME_ID: "home-1"})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "John Doe"
        assert result["data"][CONF_HOME_ID] == "home-1"
        assert result["data"][CONF_USER_ID] == "test-user"
        mock_set_unique.assert_called_once_with("test-user")


async def test_select_home_success_with_email(hass: HomeAssistant) -> None:
    """Test successful home selection with email (no nickname)."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_user = MagicMock()
    mock_user.user_id = "test-user"
    mock_user.email = "test@example.com"
    mock_user.nickname = None
    mock_user.get_display_name.return_value = "test@example.com"

    mock_home = MagicMock()
    mock_home.home_id = "home-1"
    mock_home.home_name = "My Home"
    mock_home.device_count = 5

    flow._auth_info.user_info = mock_user
    flow._auth_info.homes = [mock_home]
    flow._auth_info.auth_data = {CONF_TOKEN: {"access_token": "test"}}

    with (
        patch.object(flow, "async_set_unique_id"),
        patch.object(flow, "_abort_if_unique_id_configured"),
    ):
        result = await flow.async_step_select_home(user_input={CONF_HOME_ID: "home-1"})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "test@example.com"


async def test_select_home_success_default_title(hass: HomeAssistant) -> None:
    """Test successful home selection with default title."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_user = MagicMock()
    mock_user.user_id = "test-user"
    mock_user.email = None
    mock_user.nickname = None
    mock_user.get_display_name.return_value = None

    mock_home = MagicMock()
    mock_home.home_id = "home-1"
    mock_home.home_name = "My Home"
    mock_home.device_count = 5

    flow._auth_info.user_info = mock_user
    flow._auth_info.homes = [mock_home]
    flow._auth_info.auth_data = {CONF_TOKEN: {"access_token": "test"}}

    with (
        patch.object(flow, "async_set_unique_id"),
        patch.object(flow, "_abort_if_unique_id_configured"),
    ):
        result = await flow.async_step_select_home(user_input={CONF_HOME_ID: "home-1"})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Heiman Home"


async def test_get_home_selection_schema_empty_homes() -> None:
    """Test home selection schema with empty homes list."""
    flow = HeimanConfigFlow()
    flow._auth_info.homes = []

    schema = flow._get_home_selection_schema()
    assert schema.schema == {}


async def test_get_home_selection_schema_with_homes() -> None:
    """Test home selection schema with valid homes."""
    flow = HeimanConfigFlow()

    mock_home1 = MagicMock()
    mock_home1.home_id = "home-1"
    mock_home1.home_name = "Home 1"
    mock_home1.device_count = 5

    mock_home2 = MagicMock()
    mock_home2.home_id = "home-2"
    mock_home2.home_name = "Home 2"
    mock_home2.device_count = 10

    flow._auth_info.homes = [mock_home1, mock_home2]

    schema = flow._get_home_selection_schema()
    assert isinstance(schema, vol.Schema)
    assert CONF_HOME_ID in schema.schema


async def test_get_home_selection_schema_home_without_id() -> None:
    """Test home selection schema skips homes without ID."""
    flow = HeimanConfigFlow()

    mock_home1 = MagicMock()
    mock_home1.home_id = ""  # Empty ID should be skipped
    mock_home1.home_name = "Home 1"
    mock_home1.device_count = 5

    mock_home2 = MagicMock()
    mock_home2.home_id = "home-2"
    mock_home2.home_name = "Home 2"
    mock_home2.device_count = 10

    flow._auth_info.homes = [mock_home1, mock_home2]

    schema = flow._get_home_selection_schema()
    # Should only have home-2
    assert isinstance(schema, vol.Schema)
    assert CONF_HOME_ID in schema.schema


async def test_get_home_selection_schema_all_homes_without_id(
    hass: HomeAssistant,
) -> None:
    """Test home selection schema when all homes lack ID."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_home1 = MagicMock()
    mock_home1.home_id = ""
    mock_home1.home_name = "Home 1"
    mock_home1.device_count = 5

    mock_home2 = MagicMock()
    mock_home2.home_id = None
    mock_home2.home_name = "Home 2"
    mock_home2.device_count = 10

    flow._auth_info.homes = [mock_home1, mock_home2]

    # Should return empty schema when no valid homes found
    result = flow._get_home_selection_schema()
    assert isinstance(result, vol.Schema)
    # Empty schema indicates no valid homes
    assert not result.schema


async def test_select_home_all_homes_without_id_aborts(
    hass: HomeAssistant,
) -> None:
    """Test that select_home step aborts when all homes lack valid ID."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    # Create auth info with homes that have no valid home_id
    mock_user_info = MagicMock()
    mock_user_info.user_id = "test_user"
    mock_user_info.email = "test@example.com"
    mock_user_info.get_display_name.return_value = "Test User"

    mock_home1 = MagicMock()
    mock_home1.home_id = ""
    mock_home1.home_name = "Home 1"
    mock_home1.device_count = 5

    mock_home2 = MagicMock()
    mock_home2.home_id = None
    mock_home2.home_name = "Home 2"
    mock_home2.device_count = 10

    flow._auth_info.user_info = mock_user_info
    flow._auth_info.homes = [mock_home1, mock_home2]
    flow._auth_info.auth_data = {"token": "test_token"}

    # Call async_step_select_home without user_input (showing form)
    result = await flow.async_step_select_home()

    # Should abort because all homes have invalid home_id
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_home_data"


async def test_async_step_reauth(hass: HomeAssistant) -> None:
    """Test async_step_reauth returns reauth_confirm form."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    result = await flow.async_step_reauth({})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_async_step_reauth_confirm_show_form(hass: HomeAssistant) -> None:
    """Test async_step_reauth_confirm shows form when no user input."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    result = await flow.async_step_reauth_confirm()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_async_step_reauth_confirm_restart_oauth(hass: HomeAssistant) -> None:
    """Test async_step_reauth_confirm restarts OAuth flow (line 153)."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    with patch.object(flow, "async_step_user") as mock_step_user:
        mock_step_user.return_value = {"type": FlowResultType.EXTERNAL_STEP}
        result = await flow.async_step_reauth_confirm({})

        mock_step_user.assert_called_once()
        assert result["type"] is FlowResultType.EXTERNAL_STEP


async def test_async_step_select_home_reauth_wrong_account(
    hass: HomeAssistant,
) -> None:
    """Test select_home reauth aborts on wrong account (line 97)."""
    flow = HeimanConfigFlow()
    flow.hass = hass
    # Set source via context
    flow.context = {"source": SOURCE_REAUTH}

    # Mock auth info with current user
    mock_user_info = MagicMock()
    mock_user_info.user_id = "current-user-id"
    mock_user_info.email = "test@example.com"
    mock_user_info.get_display_name = MagicMock(return_value="Test User")

    mock_home = MagicMock()
    mock_home.home_id = "home-1"
    mock_home.home_name = "Home 1"
    mock_home.device_count = 5

    flow._auth_info = AuthInfo()
    flow._auth_info.user_info = mock_user_info
    flow._auth_info.homes = [mock_home]
    flow._auth_info.auth_data = {"token": "test_token"}

    # Set unique_id to current user
    await flow.async_set_unique_id("current-user-id")

    # Mock _abort_if_unique_id_mismatch to raise AbortFlow
    with patch.object(
        flow,
        "_abort_if_unique_id_mismatch",
        side_effect=lambda reason="unique_id_mismatch", description_placeholders=None: (
            _ for _ in ()
        ).throw(Exception(f"Aborted: {reason}")),
    ):
        # Select a home - should call _abort_if_unique_id_mismatch
        with pytest.raises(Exception, match="reauth_account_mismatch"):
            await flow.async_step_select_home({CONF_HOME_ID: "home-1"})


async def test_async_step_select_home_reauth_success(
    hass: HomeAssistant,
) -> None:
    """Test select_home reauth updates and reloads entry (lines 98-105)."""
    flow = HeimanConfigFlow()
    flow.hass = hass
    # Set source via context with entry_id
    flow.context = {"source": SOURCE_REAUTH, "entry_id": "test-entry-id"}

    # Mock auth info
    mock_user_info = MagicMock()
    mock_user_info.user_id = "test-user-id"
    mock_user_info.email = "test@example.com"
    mock_user_info.get_display_name = MagicMock(return_value="Test User")

    mock_home = MagicMock()
    mock_home.home_id = "home-1"
    mock_home.home_name = "Home 1"
    mock_home.device_count = 5

    flow._auth_info = AuthInfo()
    flow._auth_info.user_info = mock_user_info
    flow._auth_info.homes = [mock_home]
    flow._auth_info.auth_data = {"token": "new_token"}

    # Set unique_id to match
    await flow.async_set_unique_id("test-user-id")

    # Mock _abort_if_unique_id_mismatch to do nothing (no mismatch)
    # Mock _get_reauth_entry to return a mock entry
    mock_entry = MagicMock()
    mock_entry.unique_id = "test-user-id"

    with (
        patch.object(flow, "_abort_if_unique_id_mismatch"),
        patch.object(flow, "_get_reauth_entry", return_value=mock_entry),
        patch.object(flow, "async_update_reload_and_abort") as mock_update_reload,
    ):
        mock_update_reload.return_value = {"type": FlowResultType.ABORT}

        # Select a home
        await flow.async_step_select_home({CONF_HOME_ID: "home-1"})

        # Verify update_reload_and_abort was called with correct data
        mock_update_reload.assert_called_once()
        call_args = mock_update_reload.call_args
        # First arg is the entry
        assert call_args[0][0] == mock_entry
        data_updates = call_args[1]["data_updates"]
        assert data_updates["token"] == "new_token"
        assert data_updates[CONF_HOME_ID] == "home-1"
        assert data_updates[CONF_USER_ID] == "test-user-id"
