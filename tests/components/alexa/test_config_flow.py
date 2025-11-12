"""Tests for Alexa integration config_flow.py - OAuth config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import ClientError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.data_entry_flow import FlowResultType

from custom_components.alexa.config_flow import AlexaFlowHandler
from custom_components.alexa.const import DOMAIN, REQUIRED_SCOPES

from .conftest import (
    TEST_ACCESS_TOKEN,
    TEST_AUTH_CODE,
    TEST_CLIENT_ID,
    TEST_CLIENT_SECRET,
    TEST_REFRESH_TOKEN,
    TEST_USER_EMAIL,
    TEST_USER_ID,
    TEST_USER_NAME,
)


class TestAlexaFlowHandlerInit:
    """Test AlexaFlowHandler initialization and properties."""

    def test_handler_domain(self):
        """Test handler has correct domain."""
        assert AlexaFlowHandler.DOMAIN == DOMAIN
        assert AlexaFlowHandler.VERSION == 1

    def test_logger_property(self, mock_hass):
        """Test logger property returns correct logger."""
        handler = AlexaFlowHandler()
        handler.hass = mock_hass

        logger = handler.logger
        assert logger is not None
        assert logger.name == "custom_components.alexa.config_flow"

    def test_extra_authorize_data(self, mock_hass):
        """Test extra_authorize_data returns correct scope."""
        handler = AlexaFlowHandler()
        handler.hass = mock_hass

        data = handler.extra_authorize_data
        assert "scope" in data
        assert data["scope"] == REQUIRED_SCOPES
        assert data["scope"] == "profile:user_id"


class TestAsyncStepUser:
    """Test async_step_user - Initial user flow."""

    async def test_step_user_show_form(self, mock_hass):
        """Test step_user shows form when no input provided."""
        handler = AlexaFlowHandler()
        handler.hass = mock_hass

        result = await handler.async_step_user(user_input=None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        # Verify schema has required fields
        schema = result["data_schema"].schema
        assert CONF_CLIENT_ID in schema
        assert CONF_CLIENT_SECRET in schema

    async def test_step_user_registers_implementation(self, mock_hass):
        """Test step_user registers OAuth implementation with credentials."""
        handler = AlexaFlowHandler()
        handler.hass = mock_hass

        user_input = {
            CONF_CLIENT_ID: TEST_CLIENT_ID,
            CONF_CLIENT_SECRET: TEST_CLIENT_SECRET,
        }

        # Create a mock implementation to return after registration
        mock_impl = Mock()
        mock_impl.client_id = TEST_CLIENT_ID
        mock_impl.client_secret = TEST_CLIENT_SECRET

        with patch(
            "custom_components.alexa.config_flow.config_entry_oauth2_flow.async_get_implementations",
            side_effect=[{}, {DOMAIN: mock_impl}],  # First call empty, second has registered impl
        ) as mock_get_impls, patch(
            "custom_components.alexa.config_flow.config_entry_oauth2_flow.async_register_implementation"
        ) as mock_register, patch.object(
            handler, "async_step_auth", new=AsyncMock(return_value={"type": "redirect"})
        ) as mock_auth:

            result = await handler.async_step_user(user_input=user_input)

            # Verify implementation was registered
            mock_register.assert_called_once()
            args = mock_register.call_args[0]
            assert args[0] == mock_hass  # hass
            assert args[1] == DOMAIN  # domain
            impl = args[2]  # implementation
            assert impl.client_id == TEST_CLIENT_ID
            assert impl.client_secret == TEST_CLIENT_SECRET

            # Verify flow proceeded to auth step
            mock_auth.assert_called_once()

    async def test_step_user_implementation_already_registered(self, mock_hass):
        """Test step_user uses existing implementation if already registered."""
        handler = AlexaFlowHandler()
        handler.hass = mock_hass

        user_input = {
            CONF_CLIENT_ID: TEST_CLIENT_ID,
            CONF_CLIENT_SECRET: TEST_CLIENT_SECRET,
        }

        mock_impl = Mock()
        mock_impl.client_id = TEST_CLIENT_ID
        mock_impl.client_secret = TEST_CLIENT_SECRET

        with patch(
            "custom_components.alexa.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={DOMAIN: mock_impl},  # Already registered
        ) as mock_get_impls, patch(
            "custom_components.alexa.config_flow.config_entry_oauth2_flow.async_register_implementation"
        ) as mock_register, patch.object(
            handler, "async_step_auth", new=AsyncMock(return_value={"type": "redirect"})
        ) as mock_auth:

            result = await handler.async_step_user(user_input=user_input)

            # Verify implementation was NOT re-registered
            mock_register.assert_not_called()

            # Verify flow proceeded to auth step
            mock_auth.assert_called_once()

    async def test_step_user_sets_flow_impl(self, mock_hass):
        """Test step_user sets flow_impl property for framework."""
        handler = AlexaFlowHandler()
        handler.hass = mock_hass

        user_input = {
            CONF_CLIENT_ID: TEST_CLIENT_ID,
            CONF_CLIENT_SECRET: TEST_CLIENT_SECRET,
        }

        with patch(
            "custom_components.alexa.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ), patch(
            "custom_components.alexa.config_flow.config_entry_oauth2_flow.async_register_implementation"
        ), patch.object(
            handler, "async_step_auth", new=AsyncMock(return_value={"type": "redirect"})
        ):

            # Mock getting implementations after registration
            mock_impl = Mock()
            with patch(
                "custom_components.alexa.config_flow.config_entry_oauth2_flow.async_get_implementations",
                return_value={DOMAIN: mock_impl},
            ):
                result = await handler.async_step_user(user_input=user_input)

            # Verify flow_impl was set
            assert handler.flow_impl == mock_impl


class TestAsyncOAuthCreateEntry:
    """Test async_oauth_create_entry - Create entry after OAuth completes."""

    async def test_create_entry_success(
        self, mock_hass, mock_amazon_profile, mock_aiohttp_session
    ):
        """Test successful entry creation after OAuth."""
        handler = AlexaFlowHandler()
        handler.hass = mock_hass

        oauth_data = {
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            "auth_implementation": DOMAIN,
        }

        session, mock_response = mock_aiohttp_session
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_amazon_profile)

        # Mock OAuth implementation
        mock_impl = Mock()
        mock_impl.client_id = TEST_CLIENT_ID
        mock_impl.client_secret = TEST_CLIENT_SECRET

        with patch(
            "custom_components.alexa.config_flow.async_get_clientsession",
            return_value=session,
        ), patch(
            "custom_components.alexa.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={DOMAIN: mock_impl},
        ), patch.object(
            handler, "async_set_unique_id", new=AsyncMock()
        ) as mock_set_unique, patch.object(
            handler, "_abort_if_unique_id_configured", new=Mock()
        ) as mock_abort_check, patch.object(
            handler, "async_create_entry", new=Mock(return_value={"type": "create_entry"})
        ) as mock_create:

            result = await handler.async_oauth_create_entry(oauth_data)

            # Verify profile was fetched
            session.get.assert_called_once_with(
                "https://api.amazon.com/user/profile",
                headers={"Authorization": f"Bearer {TEST_ACCESS_TOKEN}"},
            )

            # Verify unique_id was set to prevent duplicates
            mock_set_unique.assert_called_once_with(TEST_USER_ID)
            mock_abort_check.assert_called_once()

            # Verify entry was created with correct data
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["title"] == f"Amazon Alexa ({TEST_USER_NAME})"

            data = call_kwargs["data"]
            assert data["auth_implementation"] == DOMAIN
            assert data["token"] == oauth_data["token"]
            assert data["user_id"] == TEST_USER_ID
            assert data["name"] == TEST_USER_NAME
            assert data["email"] == TEST_USER_EMAIL
            assert data[CONF_CLIENT_ID] == TEST_CLIENT_ID
            assert data[CONF_CLIENT_SECRET] == TEST_CLIENT_SECRET

    async def test_create_entry_profile_fetch_network_error(
        self, mock_hass, mock_aiohttp_session
    ):
        """Test entry creation aborts on network error fetching profile."""
        handler = AlexaFlowHandler()
        handler.hass = mock_hass

        oauth_data = {
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            "auth_implementation": DOMAIN,
        }

        session, mock_response = mock_aiohttp_session

        # Simulate network error
        session.get = Mock(side_effect=ClientError("Network error"))

        with patch(
            "custom_components.alexa.config_flow.async_get_clientsession",
            return_value=session,
        ), patch.object(
            handler, "async_abort", new=Mock(return_value={"type": "abort"})
        ) as mock_abort:

            result = await handler.async_oauth_create_entry(oauth_data)

            # Verify flow aborted with cannot_connect
            mock_abort.assert_called_once_with(reason="cannot_connect")

    async def test_create_entry_profile_fetch_http_error(
        self, mock_hass, mock_aiohttp_session
    ):
        """Test entry creation aborts on HTTP error from Amazon API."""
        handler = AlexaFlowHandler()
        handler.hass = mock_hass

        oauth_data = {
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            "auth_implementation": DOMAIN,
        }

        session, mock_response = mock_aiohttp_session
        mock_response.status = 401  # Unauthorized

        with patch(
            "custom_components.alexa.config_flow.async_get_clientsession",
            return_value=session,
        ), patch.object(
            handler, "async_abort", new=Mock(return_value={"type": "abort"})
        ) as mock_abort:

            result = await handler.async_oauth_create_entry(oauth_data)

            # Verify flow aborted with cannot_connect
            mock_abort.assert_called_once_with(reason="cannot_connect")

    async def test_create_entry_profile_missing_user_id(
        self, mock_hass, mock_aiohttp_session
    ):
        """Test entry creation aborts when profile missing user_id."""
        handler = AlexaFlowHandler()
        handler.hass = mock_hass

        oauth_data = {
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            "auth_implementation": DOMAIN,
        }

        session, mock_response = mock_aiohttp_session
        mock_response.status = 200
        # Profile missing user_id
        mock_response.json = AsyncMock(return_value={"name": TEST_USER_NAME})

        with patch(
            "custom_components.alexa.config_flow.async_get_clientsession",
            return_value=session,
        ), patch.object(
            handler, "async_abort", new=Mock(return_value={"type": "abort"})
        ) as mock_abort:

            result = await handler.async_oauth_create_entry(oauth_data)

            # Verify flow aborted with invalid_auth
            mock_abort.assert_called_once_with(reason="invalid_auth")

    async def test_create_entry_unexpected_error(
        self, mock_hass, mock_aiohttp_session
    ):
        """Test entry creation aborts on unexpected error."""
        handler = AlexaFlowHandler()
        handler.hass = mock_hass

        oauth_data = {
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            "auth_implementation": DOMAIN,
        }

        session, mock_response = mock_aiohttp_session
        mock_response.status = 200
        # Simulate JSON decode error
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))

        with patch(
            "custom_components.alexa.config_flow.async_get_clientsession",
            return_value=session,
        ), patch.object(
            handler, "async_abort", new=Mock(return_value={"type": "abort"})
        ) as mock_abort:

            result = await handler.async_oauth_create_entry(oauth_data)

            # Verify flow aborted with invalid_auth
            mock_abort.assert_called_once_with(reason="invalid_auth")

    async def test_create_entry_duplicate_account(
        self, mock_hass, mock_amazon_profile, mock_aiohttp_session
    ):
        """Test entry creation prevents duplicate accounts via unique_id."""
        handler = AlexaFlowHandler()
        handler.hass = mock_hass

        oauth_data = {
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            "auth_implementation": DOMAIN,
        }

        session, mock_response = mock_aiohttp_session
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_amazon_profile)

        mock_impl = Mock()
        mock_impl.client_id = TEST_CLIENT_ID
        mock_impl.client_secret = TEST_CLIENT_SECRET

        with patch(
            "custom_components.alexa.config_flow.async_get_clientsession",
            return_value=session,
        ), patch(
            "custom_components.alexa.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={DOMAIN: mock_impl},
        ), patch.object(
            handler, "async_set_unique_id", new=AsyncMock()
        ) as mock_set_unique, patch.object(
            handler,
            "_abort_if_unique_id_configured",
            side_effect=Exception("Already configured"),
        ):

            # Should raise exception (caught by framework)
            with pytest.raises(Exception, match="Already configured"):
                await handler.async_oauth_create_entry(oauth_data)


class TestConfigFlowIntegration:
    """Test full config flow integration scenarios."""

    async def test_full_flow_user_to_oauth_success(
        self, mock_hass, mock_amazon_profile, mock_aiohttp_session
    ):
        """Test complete flow from user initiation to entry creation."""
        handler = AlexaFlowHandler()
        handler.hass = mock_hass

        # Step 1: Show form
        result1 = await handler.async_step_user(user_input=None)
        assert result1["type"] == FlowResultType.FORM

        # Step 2: Submit credentials
        user_input = {
            CONF_CLIENT_ID: TEST_CLIENT_ID,
            CONF_CLIENT_SECRET: TEST_CLIENT_SECRET,
        }

        # Create a mock implementation to return after registration
        mock_impl = Mock()
        mock_impl.client_id = TEST_CLIENT_ID
        mock_impl.client_secret = TEST_CLIENT_SECRET

        with patch(
            "custom_components.alexa.config_flow.config_entry_oauth2_flow.async_get_implementations",
            side_effect=[{}, {DOMAIN: mock_impl}],  # First call empty, second has registered impl
        ), patch(
            "custom_components.alexa.config_flow.config_entry_oauth2_flow.async_register_implementation"
        ), patch.object(
            handler, "async_step_auth", new=AsyncMock(return_value={"type": "redirect"})
        ):
            result2 = await handler.async_step_user(user_input=user_input)
            assert handler.flow_impl is not None

        # Step 3: OAuth completes (simulated)
        oauth_data = {
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            "auth_implementation": DOMAIN,
        }

        session, mock_response = mock_aiohttp_session
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_amazon_profile)

        mock_impl = Mock()
        mock_impl.client_id = TEST_CLIENT_ID
        mock_impl.client_secret = TEST_CLIENT_SECRET

        with patch(
            "custom_components.alexa.config_flow.async_get_clientsession",
            return_value=session,
        ), patch(
            "custom_components.alexa.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={DOMAIN: mock_impl},
        ), patch.object(
            handler, "async_set_unique_id", new=AsyncMock()
        ), patch.object(
            handler, "_abort_if_unique_id_configured", new=Mock()
        ), patch.object(
            handler, "async_create_entry", new=Mock(return_value={"type": "create_entry"})
        ) as mock_create:

            result3 = await handler.async_oauth_create_entry(oauth_data)

            # Verify successful entry creation
            mock_create.assert_called_once()
            assert result3["type"] == "create_entry"
