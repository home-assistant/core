"""Tests for Alexa integration __init__.py - Setup and teardown."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant

from custom_components.alexa import (
    async_migrate_entry,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.alexa.const import DOMAIN

from .conftest import (
    TEST_CLIENT_ID,
    TEST_CLIENT_SECRET,
    TEST_USER_ID,
    TEST_USER_NAME,
)


class TestAsyncSetup:
    """Test async_setup function."""

    async def test_async_setup_no_yaml_config(self, mock_hass):
        """Test async_setup succeeds when no YAML config present."""
        # Clear the pre-initialized data from mock_hass fixture
        mock_hass.data = {}

        config = {}
        result = await async_setup(mock_hass, config)

        assert result is True
        assert DOMAIN in mock_hass.data
        assert mock_hass.data[DOMAIN] == {}

    async def test_async_setup_with_yaml_config_warns(self, mock_hass):
        """Test async_setup warns when YAML config is present."""
        config = {DOMAIN: {"some_key": "some_value"}}

        with patch("custom_components.alexa._LOGGER.warning") as mock_warning:
            result = await async_setup(mock_hass, config)

            assert result is True
            mock_warning.assert_called_once()
            # Verify warning message mentions YAML not supported
            warning_msg = mock_warning.call_args[0][0]
            assert "YAML configuration" in warning_msg
            assert "not supported" in warning_msg


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    async def test_async_setup_entry_success(self, mock_hass, mock_config_entry):
        """Test successful setup of config entry."""
        with patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ) as mock_get_impls, patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_register_implementation"
        ) as mock_register, patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_impl, patch(
            "custom_components.alexa.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_class:

            # Setup mocks
            mock_impl = Mock()
            mock_impl.client_id = TEST_CLIENT_ID
            mock_impl.client_secret = TEST_CLIENT_SECRET
            mock_get_impl.return_value = mock_impl

            mock_session = Mock()
            mock_session.async_ensure_token_valid = AsyncMock()
            mock_session_class.return_value = mock_session

            # Run setup
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify success
            assert result is True
            mock_register.assert_called_once()
            mock_session.async_ensure_token_valid.assert_called_once()

            # Verify data stored
            assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]
            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            assert entry_data["session"] == mock_session
            assert entry_data["implementation"] == mock_impl
            assert entry_data["user_id"] == TEST_USER_ID
            assert entry_data["name"] == TEST_USER_NAME

    async def test_async_setup_entry_already_registered(
        self, mock_hass, mock_config_entry
    ):
        """Test setup when OAuth implementation is already registered."""
        with patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_implementations",
            return_value={DOMAIN: Mock()},  # Already registered
        ) as mock_get_impls, patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_register_implementation"
        ) as mock_register, patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_impl, patch(
            "custom_components.alexa.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_class:

            # Setup mocks
            mock_impl = Mock()
            mock_impl.client_id = TEST_CLIENT_ID
            mock_impl.client_secret = TEST_CLIENT_SECRET
            mock_get_impl.return_value = mock_impl

            mock_session = Mock()
            mock_session.async_ensure_token_valid = AsyncMock()
            mock_session_class.return_value = mock_session

            # Run setup
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify success without re-registering
            assert result is True
            mock_register.assert_not_called()

    async def test_async_setup_entry_missing_client_id(self, mock_hass):
        """Test setup fails when client_id is missing."""
        bad_entry = ConfigEntry(
            version=1,
            minor_version=0,
            domain=DOMAIN,
            title="Amazon Alexa",
            data={
                "auth_implementation": DOMAIN,
                CONF_CLIENT_SECRET: TEST_CLIENT_SECRET,
                # Missing CONF_CLIENT_ID
            },
            source="user",
            entry_id="test_entry_bad",
            unique_id="user_bad",
            discovery_keys={},
            options={},
            subentries_data=[],
        )

        with patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ), patch(
            "custom_components.alexa._LOGGER.error"
        ) as mock_error:
            result = await async_setup_entry(mock_hass, bad_entry)

            assert result is False
            mock_error.assert_called_once()
            error_msg = mock_error.call_args[0][0]
            assert "Missing client_id or client_secret" in error_msg

    async def test_async_setup_entry_missing_client_secret(self, mock_hass):
        """Test setup fails when client_secret is missing."""
        bad_entry = ConfigEntry(
            version=1,
            minor_version=0,
            domain=DOMAIN,
            title="Amazon Alexa",
            data={
                "auth_implementation": DOMAIN,
                CONF_CLIENT_ID: TEST_CLIENT_ID,
                # Missing CONF_CLIENT_SECRET
            },
            source="user",
            entry_id="test_entry_bad2",
            unique_id="user_bad2",
            discovery_keys={},
            options={},
            subentries_data=[],
        )

        with patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ), patch(
            "custom_components.alexa._LOGGER.error"
        ) as mock_error:
            result = await async_setup_entry(mock_hass, bad_entry)

            assert result is False
            mock_error.assert_called_once()

    async def test_async_setup_entry_get_implementation_fails(
        self, mock_hass, mock_config_entry
    ):
        """Test setup fails when getting implementation fails."""
        with patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ), patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_register_implementation"
        ), patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_config_entry_implementation",
            side_effect=ValueError("Implementation not found"),
        ) as mock_get_impl, patch(
            "custom_components.alexa._LOGGER.error"
        ) as mock_error:

            result = await async_setup_entry(mock_hass, mock_config_entry)

            assert result is False
            mock_error.assert_called_once()
            error_msg = mock_error.call_args[0][0]
            assert "Failed to get OAuth implementation" in error_msg

    async def test_async_setup_entry_token_validation_fails(
        self, mock_hass, mock_config_entry
    ):
        """Test setup continues even if token validation fails."""
        with patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ), patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_register_implementation"
        ), patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_impl, patch(
            "custom_components.alexa.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_class:

            # Setup mocks
            mock_impl = Mock()
            mock_impl.client_id = TEST_CLIENT_ID
            mock_impl.client_secret = TEST_CLIENT_SECRET
            mock_get_impl.return_value = mock_impl

            # Mock session with failing token validation
            mock_session = Mock()
            mock_session.async_ensure_token_valid = AsyncMock(
                side_effect=Exception("Token expired")
            )
            mock_session_class.return_value = mock_session

            # Run setup - should succeed despite validation failure
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Setup should continue (framework will trigger reauth)
            assert result is True
            assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]

    async def test_async_setup_entry_with_platforms(self, mock_hass, mock_config_entry):
        """Test setup forwards to platforms when PLATFORMS is defined."""
        with patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ), patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_register_implementation"
        ), patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_impl, patch(
            "custom_components.alexa.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_class, patch(
            "custom_components.alexa.PLATFORMS",
            ["notify"],  # Mock having platforms
        ):

            # Setup mocks
            mock_impl = Mock()
            mock_impl.client_id = TEST_CLIENT_ID
            mock_impl.client_secret = TEST_CLIENT_SECRET
            mock_get_impl.return_value = mock_impl

            mock_session = Mock()
            mock_session.async_ensure_token_valid = AsyncMock()
            mock_session_class.return_value = mock_session

            # Run setup
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify platforms forwarding was called
            assert result is True
            mock_hass.config_entries.async_forward_entry_setups.assert_called_once_with(
                mock_config_entry, ["notify"]
            )


class TestAsyncUnloadEntry:
    """Test async_unload_entry function."""

    async def test_async_unload_entry_success(self, mock_hass, mock_config_entry):
        """Test successful unload of config entry."""
        # Setup entry data
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = {
            "session": Mock(),
            "implementation": Mock(),
            "user_id": TEST_USER_ID,
        }

        # Run unload
        result = await async_unload_entry(mock_hass, mock_config_entry)

        # Verify success
        assert result is True
        assert mock_config_entry.entry_id not in mock_hass.data[DOMAIN]

    async def test_async_unload_entry_with_platforms(
        self, mock_hass, mock_config_entry
    ):
        """Test unload forwards to platforms when PLATFORMS is defined."""
        # Setup entry data
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = {
            "session": Mock(),
            "implementation": Mock(),
            "user_id": TEST_USER_ID,
        }

        with patch("custom_components.alexa.PLATFORMS", ["notify"]):
            # Run unload
            result = await async_unload_entry(mock_hass, mock_config_entry)

            # Verify success
            assert result is True
            mock_hass.config_entries.async_unload_platforms.assert_called_once_with(
                mock_config_entry, ["notify"]
            )

    async def test_async_unload_entry_platform_fails(
        self, mock_hass, mock_config_entry
    ):
        """Test unload fails when platform unload fails."""
        # Setup entry data
        mock_hass.data[DOMAIN][mock_config_entry.entry_id] = {
            "session": Mock(),
            "implementation": Mock(),
            "user_id": TEST_USER_ID,
        }

        # Mock platform unload failure
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        with patch("custom_components.alexa.PLATFORMS", ["notify"]), patch(
            "custom_components.alexa._LOGGER.warning"
        ) as mock_warning:

            # Run unload
            result = await async_unload_entry(mock_hass, mock_config_entry)

            # Verify failure
            assert result is False
            mock_warning.assert_called_once()
            # Entry data should not be cleaned up if unload failed
            assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]

    async def test_async_unload_entry_no_data(self, mock_hass, mock_config_entry):
        """Test unload succeeds even if entry data doesn't exist."""
        # Don't add entry data - simulate already cleaned up

        # Run unload
        result = await async_unload_entry(mock_hass, mock_config_entry)

        # Verify success (graceful handling of missing data)
        assert result is True


class TestAsyncMigrateEntry:
    """Test async_migrate_entry function."""

    async def test_migrate_entry_version_1_current(self, mock_hass, mock_config_entry):
        """Test migration succeeds for current version 1."""
        # Entry is already version 1
        assert mock_config_entry.version == 1

        result = await async_migrate_entry(mock_hass, mock_config_entry)

        assert result is True

    async def test_migrate_entry_unknown_version(self, mock_hass):
        """Test migration fails for unknown version."""
        bad_entry = ConfigEntry(
            version=99,  # Unknown future version
            minor_version=0,
            domain=DOMAIN,
            title="Amazon Alexa",
            data={"auth_implementation": DOMAIN},
            source="user",
            entry_id="test_entry_unknown",
            unique_id="user_unknown",
            discovery_keys={},
            options={},
            subentries_data=[],
        )

        with patch("custom_components.alexa._LOGGER.error") as mock_error:
            result = await async_migrate_entry(mock_hass, bad_entry)

            assert result is False
            mock_error.assert_called_once()
            # Check both the message template and the argument
            call_args = mock_error.call_args[0]
            error_msg = call_args[0]
            assert "Unknown config entry version" in error_msg
            # The version number is passed as the second argument
            if len(call_args) > 1:
                assert call_args[1] == 99


class TestIntegrationInitialization:
    """Test integration data initialization."""

    async def test_domain_data_initialization(self, mock_hass):
        """Test that domain data is properly initialized."""
        config = {}
        await async_setup(mock_hass, config)

        assert DOMAIN in mock_hass.data
        assert isinstance(mock_hass.data[DOMAIN], dict)

    async def test_multiple_entries_share_domain_data(
        self, mock_hass, mock_config_entry
    ):
        """Test that multiple config entries share the same domain data."""
        # Setup first entry
        with patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ), patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_register_implementation"
        ), patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_impl, patch(
            "custom_components.alexa.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_class:

            mock_impl = Mock()
            mock_impl.client_id = TEST_CLIENT_ID
            mock_impl.client_secret = TEST_CLIENT_SECRET
            mock_get_impl.return_value = mock_impl

            mock_session = Mock()
            mock_session.async_ensure_token_valid = AsyncMock()
            mock_session_class.return_value = mock_session

            await async_setup_entry(mock_hass, mock_config_entry)

        # Create second entry
        entry2 = ConfigEntry(
            version=1,
            minor_version=0,
            domain=DOMAIN,
            title="Amazon Alexa (User 2)",
            data={
                "auth_implementation": DOMAIN,
                "token": {"access_token": "token2"},
                "user_id": "user2",
                CONF_CLIENT_ID: TEST_CLIENT_ID,
                CONF_CLIENT_SECRET: TEST_CLIENT_SECRET,
            },
            source="user",
            entry_id="test_entry_id_456",
            unique_id="user2",
            discovery_keys={},
            options={},
            subentries_data=[],
        )

        # Setup second entry
        with patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_implementations",
            return_value={DOMAIN: Mock()},  # Already registered
        ), patch(
            "custom_components.alexa.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_impl2, patch(
            "custom_components.alexa.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_class2:

            mock_get_impl2.return_value = mock_impl
            mock_session2 = Mock()
            mock_session2.async_ensure_token_valid = AsyncMock()
            mock_session_class2.return_value = mock_session2

            await async_setup_entry(mock_hass, entry2)

        # Verify both entries in same domain data
        assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]
        assert entry2.entry_id in mock_hass.data[DOMAIN]
        assert len(mock_hass.data[DOMAIN]) == 3  # 2 entries + pkce dict
