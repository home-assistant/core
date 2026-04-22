"""Common fixtures for the Heiman Home tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.heiman_home import const as heiman_const
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

__all__ = [
    "MockConfigEntry",
]


@pytest.fixture(autouse=True)
async def clear_entries_before_test(hass: HomeAssistant) -> None:
    """Clear config entries before each test to ensure isolation."""
    # Clean up any existing entries from previous tests
    for entry in hass.config_entries.async_entries(heiman_const.DOMAIN):
        await hass.config_entries.async_remove(entry.entry_id)


@pytest.fixture(name="setup_credentials", autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        heiman_const.DOMAIN,
        ClientCredential("client-id", "client-secret"),
        heiman_const.DOMAIN,
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=heiman_const.DOMAIN,
        data={
            "token": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_in": 3600,
            },
            "home_id": "test-home-id",
            "user_id": "test-user-id",
        },
        unique_id="test-user-id",
    )


@pytest.fixture
def mock_api_client() -> Generator[MagicMock]:
    """Mock the Heiman API client."""
    with patch(
        "homeassistant.components.heiman_home.api.HeimanApiClient",
    ) as mock_client:
        client = mock_client.return_value
        # Set up cloud_client mock
        mock_cloud = MagicMock()
        mock_cloud.async_get_user_info = AsyncMock()
        mock_cloud.async_get_homes = AsyncMock()
        mock_cloud.async_get_devices = AsyncMock(return_value={})
        mock_cloud.async_get_device_detail = AsyncMock(return_value=None)
        mock_cloud.async_get_device_properties = AsyncMock()
        mock_cloud._async_get_device_detail = AsyncMock(return_value=None)
        client.cloud_client = mock_cloud
        # Set up async_ensure_token_valid as it's called by the coordinator
        client.async_ensure_token_valid = AsyncMock()
        # Keep legacy methods pointing to cloud_client
        client.async_get_user_info = mock_cloud.async_get_user_info
        client.async_get_homes = mock_cloud.async_get_homes
        client.async_get_devices = mock_cloud.async_get_devices
        client.async_get_device_detail = mock_cloud.async_get_device_detail
        client.async_get_device_properties = mock_cloud.async_get_device_properties
        yield client


@pytest.fixture
def mock_coordinator() -> Generator[AsyncMock]:
    """Mock the Heiman coordinator."""
    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator",
        autospec=True,
    ) as mock_coord:
        coordinator = mock_coord.return_value
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.async_init_mqtt_client = AsyncMock()
        coordinator.data = MagicMock()
        coordinator.data.user_info = None
        coordinator.data.home_info = None
        coordinator.data.devices = {}
        yield coordinator


@pytest.fixture
def mock_mqtt_client() -> Generator[AsyncMock]:
    """Mock the MQTT client."""
    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanMqttClient",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        client.subscribe = AsyncMock()
        client.unsubscribe = AsyncMock()
        yield client


@pytest.fixture
def mock_device_management() -> Generator[MagicMock]:
    """Mock device management."""
    with patch(
        "heimanconnect.DeviceManagement",
        autospec=True,
    ) as mock_dm:
        dm = mock_dm.return_value
        dm.filter_manager.get_filtered_devices = MagicMock(return_value=[])
        yield dm
