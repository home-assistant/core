"""Common fixtures for the Appwrite config flow tests."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.appwrite.const import CONF_PROJECT_ID, DOMAIN
from homeassistant.components.appwrite.services import AppwriteServices
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service import async_set_service_schema


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.appwrite.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_appwrite_client():
    """Create a mock Appwrite client."""
    return Mock()


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Create a mock config entry."""
    config_entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Appwrite",
        data={
            CONF_HOST: "http://test.appwrite.io",
            CONF_PROJECT_ID: "test-project",
            CONF_API_KEY: "test-api-key",
        },
        source="test",
        options={},
        unique_id="test-unique-id",
        entry_id="test-entry-id",
        discovery_keys=None,
        minor_version=1,
    )
    config_entry.runtime_data = Mock()
    return config_entry


@pytest.fixture
def mock_services_yaml() -> dict:
    """Create mock services.yaml content."""
    return {
        "execute_function": {
            "fields": {
                "function_id": {
                    "required": True,
                    "example": "123456789",
                    "selector": {"text": {}},
                },
                "function_body": {
                    "required": False,
                    "example": '{"key": "value"}',
                    "selector": {"text": {}},
                },
            }
        }
    }


@pytest.fixture
def mock_integration(mock_services_yaml) -> Mock:
    """Create a mock integration."""
    integration = Mock()
    integration.file_path = Path("/mock/path")
    return integration


@pytest.fixture
async def appwrite_services(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_appwrite_client: Mock
) -> AppwriteServices:
    """Set up Appwrite services with all necessary mocks."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_config_entry.entry_id] = mock_appwrite_client
    mock_config_entry.runtime_data = mock_appwrite_client

    with (
        patch(
            "homeassistant.loader.async_get_integration",
            return_value=mock_integration,
        ),
        patch(
            "homeassistant.util.yaml.load_yaml_dict",
            return_value=mock_services_yaml,
        ),
        patch(
            "homeassistant.helpers.service.async_set_service_schema",
            side_effect=async_set_service_schema,
        ),
    ):
        services = AppwriteServices(hass, mock_config_entry)
        await services.setup()
        return services
