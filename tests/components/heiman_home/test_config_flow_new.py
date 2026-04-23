"""Tests for Heiman Home config flow - comprehensive coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

from heimanconnect import HeimanAuthError, HeimanTokenExpiredError
import voluptuous as vol

from homeassistant.components.heiman_home.config_flow import AuthInfo, HeimanConfigFlow
from homeassistant.components.heiman_home.const import CONF_HOME_ID, CONF_USER_ID
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
    mock_api_client._ensure_initialized = AsyncMock()

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
    mock_api_client._ensure_initialized = AsyncMock()

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
    mock_api_client._ensure_initialized = AsyncMock()

    with patch(
        "homeassistant.components.heiman_home.config_flow.HeimanApiClient",
        return_value=mock_api_client,
    ):
        result = await flow.async_oauth_create_entry(
            {CONF_TOKEN: {"access_token": "test"}}
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "user_info_failed"
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
    mock_api_client._ensure_initialized = AsyncMock()

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
    mock_api_client._ensure_initialized = AsyncMock()

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
    mock_api_client._ensure_initialized = AsyncMock()

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
    mock_api_client._ensure_initialized = AsyncMock()

    with patch(
        "homeassistant.components.heiman_home.config_flow.HeimanApiClient",
        return_value=mock_api_client,
    ):
        result = await flow.async_oauth_create_entry(
            {CONF_TOKEN: {"access_token": "test"}}
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "homes_fetch_failed"
        mock_api_client.close.assert_called_once()


async def test_oauth_create_entry_success_single_home(hass: HomeAssistant) -> None:
    """Test successful OAuth entry creation with single home."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_user = MagicMock()
    mock_user.user_id = "test-user"
    mock_user.email = "test@example.com"
    mock_user.nick_name = None

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
    mock_api_client._ensure_initialized = AsyncMock()

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
    mock_user.nick_name = "John Doe"

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
    mock_user.nick_name = None

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
    mock_user.nick_name = None

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


async def test_get_home_selection_schema_all_homes_without_id() -> None:
    """Test home selection schema when all homes lack ID."""
    flow = HeimanConfigFlow()

    mock_home1 = MagicMock()
    mock_home1.home_id = ""
    mock_home1.home_name = "Home 1"
    mock_home1.device_count = 5

    mock_home2 = MagicMock()
    mock_home2.home_id = None
    mock_home2.home_name = "Home 2"
    mock_home2.device_count = 10

    flow._auth_info.homes = [mock_home1, mock_home2]

    schema = flow._get_home_selection_schema()
    assert schema.schema == {}


async def test_oauth_create_entry_reauth_flow(hass: HomeAssistant) -> None:
    """Test OAuth entry creation with re-authentication source."""
    from homeassistant.config_entries import SOURCE_REAUTH

    flow = HeimanConfigFlow()
    flow.hass = hass
    # Set source by updating context directly
    flow.context = {"source": SOURCE_REAUTH, "entry_id": "test-entry-id"}

    mock_user = MagicMock()
    mock_user.user_id = "test-user"
    mock_user.nick_name = "Test User"

    mock_home = MagicMock()
    mock_home.home_id = "home-123"
    mock_home.home_name = "My Home"
    mock_home.device_count = 5

    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=mock_user)
    mock_wrapper.async_get_homes = AsyncMock([mock_home])
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client.close = AsyncMock()
    mock_api_client._ensure_initialized = AsyncMock()

    # Mock the reauth entry
    mock_reauth_entry = MagicMock()
    mock_reauth_entry.data = {CONF_HOME_ID: "home-123"}
    mock_reauth_entry.entry_id = "test-entry-id"

    with (
        patch(
            "homeassistant.components.heiman_home.config_flow.HeimanApiClient",
            return_value=mock_api_client,
        ),
        patch.object(flow, "_get_reauth_entry", return_value=mock_reauth_entry),
        patch.object(flow, "async_update_reload_and_abort") as mock_update,
    ):
        mock_update.return_value = {
            "type": FlowResultType.ABORT,
            "reason": "reauth_successful",
        }

        result = await flow.async_oauth_create_entry(
            {CONF_TOKEN: {"access_token": "new_token"}}
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        mock_api_client.close.assert_called_once()


async def test_oauth_create_entry_reauth_with_email_title(hass: HomeAssistant) -> None:
    """Test re-auth flow when user has email but no nick_name."""
    from homeassistant.config_entries import SOURCE_REAUTH

    flow = HeimanConfigFlow()
    flow.hass = hass
    # Set source by updating context directly
    flow.context = {"source": SOURCE_REAUTH, "entry_id": "test-entry-id"}

    mock_user = MagicMock()
    mock_user.user_id = "test-user"
    mock_user.nick_name = None  # No nick_name
    mock_user.email = "user@example.com"

    mock_home = MagicMock()
    mock_home.home_id = "home-123"

    mock_api_client = MagicMock()
    mock_wrapper = MagicMock()
    mock_wrapper.async_get_user_info = AsyncMock(return_value=mock_user)
    mock_wrapper.async_get_homes = AsyncMock([mock_home])
    mock_api_client.cloud_client = mock_wrapper
    mock_api_client.close = AsyncMock()
    mock_api_client._ensure_initialized = AsyncMock()

    mock_reauth_entry = MagicMock()
    mock_reauth_entry.data = {CONF_HOME_ID: "home-123"}

    with (
        patch(
            "homeassistant.components.heiman_home.config_flow.HeimanApiClient",
            return_value=mock_api_client,
        ),
        patch.object(flow, "_get_reauth_entry", return_value=mock_reauth_entry),
        patch.object(flow, "async_update_reload_and_abort") as mock_update,
    ):
        mock_update.return_value = {
            "type": FlowResultType.ABORT,
            "reason": "reauth_successful",
        }

        result = await flow.async_oauth_create_entry(
            {CONF_TOKEN: {"access_token": "new_token"}}
        )

        assert result["type"] is FlowResultType.ABORT
        # Verify title would use email
        call_args = mock_update.call_args
        assert call_args[1]["title"] == "user@example.com"


async def test_reauth_confirm_step_show_form(hass: HomeAssistant) -> None:
    """Test reauth confirm step shows form."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    mock_reauth_entry = MagicMock()
    mock_reauth_entry.title = "Heiman Home Account"

    with patch.object(flow, "_get_reauth_entry", return_value=mock_reauth_entry):
        result = await flow.async_step_reauth_confirm()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["description_placeholders"]["name"] == "Heiman Home Account"


async def test_reauth_confirm_step_user_confirmed(hass: HomeAssistant) -> None:
    """Test reauth confirm step when user confirms."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    with patch.object(flow, "async_step_pick_implementation") as mock_pick:
        mock_pick.return_value = {
            "type": FlowResultType.EXTERNAL_STEP,
            "step_id": "auth",
        }

        result = await flow.async_step_reauth_confirm(user_input={})

        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth"
        mock_pick.assert_called_once()


async def test_reauth_step_calls_confirm(hass: HomeAssistant) -> None:
    """Test reauth step calls reauth_confirm."""
    flow = HeimanConfigFlow()
    flow.hass = hass

    with patch.object(flow, "async_step_reauth_confirm") as mock_confirm:
        mock_confirm.return_value = {
            "type": FlowResultType.FORM,
            "step_id": "reauth_confirm",
        }

        result = await flow.async_step_reauth({})

        assert result["type"] is FlowResultType.FORM
        mock_confirm.assert_called_once()
