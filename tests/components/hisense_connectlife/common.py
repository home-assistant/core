"""Common test fixtures for Hisense ConnectLife integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.application_credentials import ApplicationCredentials
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from custom_components.hisense_connectlife.const import DOMAIN


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    return hass


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.domain = DOMAIN
    entry.entry_id = "test_entry_id"
    entry.title = "Test Hisense ConnectLife"
    entry.data = {
        "auth_implementation": "test_auth_impl",
        "token": {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "expires_at": 1234567890,
        },
    }
    return entry


@pytest.fixture
def mock_application_credentials():
    """Mock Application Credentials."""
    with patch("custom_components.hisense_connectlife.auth.config_entry_oauth2_flow") as mock_oauth2:
        mock_session = AsyncMock()
        mock_session.async_ensure_token_valid = AsyncMock(
            return_value={
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_in": 3600,
                "expires_at": 1234567890,
            }
        )
        mock_oauth2.OAuth2Session.return_value = mock_session
        yield mock_session


@pytest.fixture
def mock_api_client():
    """Mock API client."""
    with patch("custom_components.hisense_connectlife.api.HisenseApiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.async_get_devices = AsyncMock(return_value=[])
        mock_instance.async_control_device = AsyncMock(return_value=True)
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_coordinator():
    """Mock data update coordinator."""
    with patch("custom_components.hisense_connectlife.coordinator.HisenseACPluginDataUpdateCoordinator") as mock_coord:
        mock_instance = AsyncMock()
        mock_instance.async_setup = AsyncMock(return_value=True)
        mock_instance.data = {}
        mock_coord.return_value = mock_instance
        yield mock_instance
