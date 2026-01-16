"""Test utilities for the Imou integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.imou.const import (
    CONF_API_URL_SG,
    DOMAIN,
    PARAM_API_URL,
    PARAM_APP_ID,
    PARAM_APP_SECRET,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_APP_ID = "test_app_id"
TEST_APP_SECRET = "test_app_secret"
TEST_API_URL = CONF_API_URL_SG

USER_INPUT = {
    PARAM_APP_ID: TEST_APP_ID,
    PARAM_APP_SECRET: TEST_APP_SECRET,
    PARAM_API_URL: TEST_API_URL,
}

CONFIG_ENTRY_DATA = {
    PARAM_APP_ID: TEST_APP_ID,
    PARAM_APP_SECRET: TEST_APP_SECRET,
    PARAM_API_URL: TEST_API_URL,
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


async def async_init_integration(
    hass: HomeAssistant,
    config_entry_data: dict | None = None,
) -> MockConfigEntry:
    """Set up the Imou integration in Home Assistant."""
    if config_entry_data is None:
        config_entry_data = CONFIG_ENTRY_DATA

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_entry_data,
        unique_id=config_entry_data.get(PARAM_APP_ID),
        entry_id="test_entry_id",
    )
    config_entry.add_to_hass(hass)

    mock_device_manager = create_mock_device_manager()

    with (
        patch(
            "homeassistant.components.imou.ImouOpenApiClient",
            return_value=create_mock_api_client(),
        ),
        patch(
            "homeassistant.components.imou.ImouHaDeviceManager",
            return_value=mock_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry
