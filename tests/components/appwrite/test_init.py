"""Test the Appwrite __init__."""

from unittest.mock import AsyncMock, Mock, patch

from appwrite.client import AppwriteException
import pytest

from homeassistant.components.appwrite import (
    AppwriteServices,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.appwrite.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed


async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_appwrite_client: Mock,
    appwrite_services: AppwriteServices,
) -> None:
    """Test setting up the Appwrite integration."""
    # Setup mock for validate_credentials to succeed
    with (
        patch(
            "homeassistant.components.appwrite.AppwriteClient",
            return_value=mock_appwrite_client,
        ),
        patch(
            "homeassistant.components.appwrite.AppwriteServices",
            return_value=appwrite_services,
        ),
    ):
        assert await async_setup_entry(hass, mock_config_entry)

        # Verify data is stored correctly
        assert DOMAIN in hass.data
        assert mock_config_entry.entry_id in hass.data[DOMAIN]
        assert hass.data[DOMAIN][mock_config_entry.entry_id] == dict(
            mock_config_entry.data
        )

        # Verify client is created and stored
        assert mock_config_entry.runtime_data == mock_appwrite_client


async def test_async_setup_entry_error(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_appwrite_client: Mock,
    appwrite_services: AppwriteServices,
) -> None:
    """Test setting up the Appwrite integration."""
    # Setup mock for validate_credentials to fail
    mock_appwrite_client.async_list_functions = Mock(
        side_effect=AppwriteException("Auth failed")
    )

    with (
        patch(
            "homeassistant.components.appwrite.AppwriteClient",
            return_value=mock_appwrite_client,
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await async_setup_entry(hass, mock_config_entry)


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    appwrite_services: AppwriteServices,
) -> None:
    """Test unloading the Appwrite integration."""
    # Setup test data
    hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_config_entry.data}

    # Register a test service
    hass.services.async_register(DOMAIN, "test_service", AsyncMock())

    # Test unloading
    assert await async_unload_entry(hass, mock_config_entry)

    # Verify domain data is removed
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]

    # Verify services are removed
    assert not hass.services.async_services_for_domain(DOMAIN)
