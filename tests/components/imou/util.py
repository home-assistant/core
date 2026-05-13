"""Test utilities for the Imou integration."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.imou.const import (
    CONF_API_URL,
    CONF_APP_ID,
    CONF_APP_SECRET,
)

TEST_APP_ID = "test_app_id"
TEST_APP_SECRET = "test_app_secret"
TEST_API_URL = "sg"

USER_INPUT = {
    CONF_APP_ID: TEST_APP_ID,
    CONF_APP_SECRET: TEST_APP_SECRET,
    CONF_API_URL: TEST_API_URL,
}

CONFIG_ENTRY_DATA = {
    CONF_APP_ID: TEST_APP_ID,
    CONF_APP_SECRET: TEST_APP_SECRET,
    CONF_API_URL: TEST_API_URL,
}


def create_mock_device_manager() -> MagicMock:
    """Create a mock device manager."""
    mock_device_manager = MagicMock()
    mock_device_manager.async_get_devices = AsyncMock(return_value=[])
    mock_device_manager.async_update_device_status = AsyncMock()
    mock_device_manager.async_press_button = AsyncMock()
    return mock_device_manager


def create_mock_api_client() -> MagicMock:
    """Create a mock API client."""
    mock_client = MagicMock()
    mock_client.async_get_token = AsyncMock()
    return mock_client
