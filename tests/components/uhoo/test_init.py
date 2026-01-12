"""Tests for __init__.py with coordinator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from aiodns.error import DNSError
from aiohttp.client_exceptions import ClientConnectionError
import pytest
from uhooapi.errors import UhooError, UnauthorizedError

from homeassistant.components.uhoo import async_setup_entry, async_unload_entry
from homeassistant.components.uhoo.const import DOMAIN, PLATFORMS
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady


def create_mock_config_entry(data=None):
    """Create a mock config entry with all required attributes."""
    if data is None:
        data = {"api_key": "test-api-key-123"}

    # Create a MagicMock with ConfigEntry spec
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.version = 1
    mock_entry.domain = DOMAIN
    mock_entry.title = "uHoo (123)"
    mock_entry.data = data
    mock_entry.source = "user"
    mock_entry.unique_id = data.get("api_key", "test-api-key-123")
    mock_entry.entry_id = "test-entry-123"
    mock_entry.minor_version = 1
    mock_entry.options = {}
    mock_entry.pref_disable_new_entities = None
    mock_entry.pref_disable_polling = None
    mock_entry.disabled_by = None
    mock_entry.reason = None
    mock_entry.state = ConfigEntryState.NOT_LOADED
    mock_entry.setup_lock = asyncio.Lock()

    # Set attributes that might be needed
    mock_entry.runtime_data = None
    mock_entry.discovery_keys = {}
    mock_entry.subentries_data = {}
    mock_entry.translation_key = None
    mock_entry.translation_placeholders = None

    return mock_entry


async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_uhoo_client,
    mock_uhoo_coordinator,
    patch_async_get_clientsession,
    patch_uhoo_data_update_coordinator,
) -> None:
    """Test successful setup of a config entry."""
    config_entry = create_mock_config_entry()

    # Mock the hass.config_entries methods
    mock_forward_entry_setups = AsyncMock()
    hass.config_entries.async_forward_entry_setups = mock_forward_entry_setups

    # Call the setup function
    result = await async_setup_entry(hass, config_entry)

    # Verify the setup was successful
    assert result is True

    # Verify login and setup_devices were called
    mock_uhoo_client.login.assert_awaited_once()
    mock_uhoo_client.setup_devices.assert_awaited_once()

    # Verify first refresh was called
    mock_uhoo_coordinator.async_config_entry_first_refresh.assert_awaited_once()

    # Verify runtime data was set
    assert config_entry.runtime_data == mock_uhoo_coordinator

    # Verify platforms were set up
    mock_forward_entry_setups.assert_awaited_once_with(config_entry, PLATFORMS)


async def test_async_setup_entry_unauthorized_error_on_login(
    hass: HomeAssistant,
    mock_uhoo_client,
    patch_async_get_clientsession,
) -> None:
    """Test setup with invalid API credentials (UnauthorizedError on login)."""
    config_entry = create_mock_config_entry()

    # Simulate UnauthorizedError on login
    mock_uhoo_client.login.side_effect = UnauthorizedError("Invalid API key")

    # Should raise ConfigEntryError
    with pytest.raises(ConfigEntryError) as exc_info:
        await async_setup_entry(hass, config_entry)

    assert "Invalid API credentials" in str(exc_info.value)

    # Verify login was attempted
    mock_uhoo_client.login.assert_awaited_once()

    # Verify setup_devices was NOT called
    mock_uhoo_client.setup_devices.assert_not_called()


async def test_async_setup_entry_unauthorized_error_on_setup_devices(
    hass: HomeAssistant,
    mock_uhoo_client,
    patch_async_get_clientsession,
) -> None:
    """Test setup with UnauthorizedError during setup_devices."""
    config_entry = create_mock_config_entry()

    # Login succeeds but setup_devices fails with UnauthorizedError
    mock_uhoo_client.login.return_value = None
    mock_uhoo_client.setup_devices.side_effect = UnauthorizedError("Token expired")

    # Should raise ConfigEntryError
    with pytest.raises(ConfigEntryError) as exc_info:
        await async_setup_entry(hass, config_entry)

    assert "Invalid API credentials" in str(exc_info.value)

    # Verify both methods were called
    mock_uhoo_client.login.assert_awaited_once()
    mock_uhoo_client.setup_devices.assert_awaited_once()


async def test_async_setup_entry_connection_error_on_login(
    hass: HomeAssistant,
    mock_uhoo_client,
    patch_async_get_clientsession,
) -> None:
    """Test setup with ClientConnectionError during login."""
    config_entry = create_mock_config_entry()

    # Simulate ClientConnectionError on login
    mock_uhoo_client.login.side_effect = ClientConnectionError("Connection failed")

    # Should raise ConfigEntryNotReady
    with pytest.raises(ConfigEntryNotReady) as exc_info:
        await async_setup_entry(hass, config_entry)

    assert "Cannot connect to uHoo servers" in str(exc_info.value)

    # Verify login was attempted
    mock_uhoo_client.login.assert_awaited_once()

    # Verify setup_devices was NOT called
    mock_uhoo_client.setup_devices.assert_not_called()


async def test_async_setup_entry_dns_error_on_login(
    hass: HomeAssistant,
    mock_uhoo_client,
    patch_async_get_clientsession,
) -> None:
    """Test setup with DNSError during login."""
    config_entry = create_mock_config_entry()

    # Simulate DNSError on login
    mock_uhoo_client.login.side_effect = DNSError("DNS resolution failed")

    # Should raise ConfigEntryNotReady
    with pytest.raises(ConfigEntryNotReady) as exc_info:
        await async_setup_entry(hass, config_entry)

    assert "Cannot connect to uHoo servers" in str(exc_info.value)

    # Verify login was attempted
    mock_uhoo_client.login.assert_awaited_once()

    # Verify setup_devices was NOT called
    mock_uhoo_client.setup_devices.assert_not_called()


async def test_async_setup_entry_uhoo_error_on_login(
    hass: HomeAssistant,
    mock_uhoo_client,
    patch_async_get_clientsession,
) -> None:
    """Test setup with UhooError during login."""
    config_entry = create_mock_config_entry()

    # Simulate UhooError on login
    mock_uhoo_client.login.side_effect = UhooError("Some uhoo error")

    # Should raise ConfigEntryNotReady
    with pytest.raises(ConfigEntryNotReady) as exc_info:
        await async_setup_entry(hass, config_entry)

    assert "Some uhoo error" in str(exc_info.value)

    # Verify login was attempted
    mock_uhoo_client.login.assert_awaited_once()

    # Verify setup_devices was NOT called
    mock_uhoo_client.setup_devices.assert_not_called()


async def test_async_setup_entry_coordinator_first_refresh_fails(
    hass: HomeAssistant,
    mock_uhoo_client,
    mock_uhoo_coordinator,
    patch_async_get_clientsession,
    patch_uhoo_data_update_coordinator,
) -> None:
    """Test setup where coordinator's first refresh fails."""
    config_entry = create_mock_config_entry()

    # Mock the hass.config_entries methods
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    # Simulate successful client setup but coordinator refresh fails
    mock_uhoo_coordinator.async_config_entry_first_refresh.side_effect = Exception(
        "First refresh failed"
    )

    # Should propagate the exception
    with pytest.raises(Exception) as exc_info:
        await async_setup_entry(hass, config_entry)

    assert "First refresh failed" in str(exc_info.value)

    # Verify client setup was completed
    mock_uhoo_client.login.assert_awaited_once()
    mock_uhoo_client.setup_devices.assert_awaited_once()


async def test_async_setup_entry_platform_setup_error(
    hass: HomeAssistant,
    mock_uhoo_client,
    mock_uhoo_coordinator,
    patch_async_get_clientsession,
    patch_uhoo_data_update_coordinator,
) -> None:
    """Test setup where platform setup fails."""
    config_entry = create_mock_config_entry()

    # Mock the hass.config_entries methods
    mock_forward_entry_setups = AsyncMock(
        side_effect=Exception("Platform setup failed")
    )
    hass.config_entries.async_forward_entry_setups = mock_forward_entry_setups

    # Should propagate the exception
    with pytest.raises(Exception) as exc_info:
        await async_setup_entry(hass, config_entry)

    assert "Platform setup failed" in str(exc_info.value)

    # Verify client and coordinator setup was completed
    mock_uhoo_client.login.assert_awaited_once()
    mock_uhoo_client.setup_devices.assert_awaited_once()
    mock_uhoo_coordinator.async_config_entry_first_refresh.assert_awaited_once()


async def test_async_unload_entry_success(
    hass: HomeAssistant,
) -> None:
    """Test successful unloading of a config entry."""
    config_entry = create_mock_config_entry()

    # Mock the hass.config_entries methods
    mock_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = mock_unload_platforms

    # Call the unload function
    result = await async_unload_entry(hass, config_entry)

    # Verify the unload was successful
    assert result is True

    # Verify async_unload_platforms was called with correct parameters
    mock_unload_platforms.assert_awaited_once_with(config_entry, PLATFORMS)


async def test_async_unload_entry_failure(
    hass: HomeAssistant,
) -> None:
    """Test failed unloading of a config entry."""
    config_entry = create_mock_config_entry()

    # Mock the hass.config_entries methods
    mock_unload_platforms = AsyncMock(return_value=False)
    hass.config_entries.async_unload_platforms = mock_unload_platforms

    # Call the unload function
    result = await async_unload_entry(hass, config_entry)

    # Verify the unload failed
    assert result is False

    # Verify async_unload_platforms was called with correct parameters
    mock_unload_platforms.assert_awaited_once_with(config_entry, PLATFORMS)


async def test_async_setup_entry_missing_api_key(
    hass: HomeAssistant,
    mock_uhoo_client,
    patch_async_get_clientsession,
) -> None:
    """Test setup when API key is missing from config entry data."""
    # Create config entry without API key
    config_entry = create_mock_config_entry(data={})

    with pytest.raises(KeyError):
        await async_setup_entry(hass, config_entry)


async def test_async_setup_entry_coordinator_creation_fails(
    hass: HomeAssistant,
    mock_uhoo_client,
    patch_async_get_clientsession,
) -> None:
    """Test setup when coordinator creation fails."""
    config_entry = create_mock_config_entry()

    # Patch UhooDataUpdateCoordinator to fail (not using the fixture)
    with patch(
        "homeassistant.components.uhoo.UhooDataUpdateCoordinator",
        side_effect=Exception("Coordinator creation failed"),
    ):
        # Should propagate the exception
        with pytest.raises(Exception) as exc_info:
            await async_setup_entry(hass, config_entry)

        assert "Coordinator creation failed" in str(exc_info.value)

        # Since coordinator creation fails before login, login should NOT be called
        mock_uhoo_client.login.assert_not_called()


async def test_async_setup_entry_with_devices(
    hass: HomeAssistant,
    mock_uhoo_client,
    mock_uhoo_coordinator,
    patch_async_get_clientsession,
    patch_uhoo_data_update_coordinator,
) -> None:
    """Test setup when client has devices."""
    config_entry = create_mock_config_entry()

    # Mock the hass.config_entries methods
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    # Setup mock client with devices
    mock_uhoo_client.devices = {"device1": MagicMock(), "device2": MagicMock()}

    # Call the setup function
    result = await async_setup_entry(hass, config_entry)

    # Verify the setup was successful
    assert result is True

    # Verify client setup was called
    mock_uhoo_client.login.assert_awaited_once()
    mock_uhoo_client.setup_devices.assert_awaited_once()


async def test_async_setup_entry_with_empty_devices(
    hass: HomeAssistant,
    mock_uhoo_client,
    mock_uhoo_coordinator,
    patch_async_get_clientsession,
    patch_uhoo_data_update_coordinator,
) -> None:
    """Test setup when client has no devices."""
    config_entry = create_mock_config_entry()

    # Mock the hass.config_entries methods
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    # Setup mock client with empty devices
    mock_uhoo_client.devices = {}

    # Call the setup function
    result = await async_setup_entry(hass, config_entry)

    # Verify the setup was successful
    assert result is True

    # Verify client setup was called
    mock_uhoo_client.login.assert_awaited_once()
    mock_uhoo_client.setup_devices.assert_awaited_once()
