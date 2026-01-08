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

    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.version = 1
    mock_entry.domain = DOMAIN
    mock_entry.title = "uHoo (123)"
    mock_entry.data = data
    mock_entry.source = "user"
    mock_entry.unique_id = (
        data.get("api_key", "test-api-key-123") if data else "test-api-key-123"
    )
    mock_entry.entry_id = "test-entry-123"
    mock_entry.minor_version = 1
    mock_entry.options = {}
    mock_entry.runtime_data = None
    mock_entry.state = ConfigEntryState.NOT_LOADED
    mock_entry.setup_lock = asyncio.Lock()

    return mock_entry


@pytest.fixture
def mock_client():
    """Mock the uhooapi Client."""
    client = AsyncMock()
    client.login = AsyncMock()
    client.setup_devices = AsyncMock()
    client.devices = {}
    return client


@pytest.fixture
def mock_coordinator():
    """Mock the UhooDataUpdateCoordinator."""
    coordinator = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_session():
    """Mock the aiohttp ClientSession."""
    return MagicMock()


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_coordinator: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    config_entry = create_mock_config_entry()

    # Mock the hass.config_entries methods
    mock_forward_entry_setups = AsyncMock()
    hass.config_entries.async_forward_entry_setups = mock_forward_entry_setups

    with (
        patch(
            "homeassistant.components.uhoo.Client", return_value=mock_client
        ) as mock_client_class,
        patch(
            "homeassistant.components.uhoo.UhooDataUpdateCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.uhoo.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        # Call the setup function
        result = await async_setup_entry(hass, config_entry)

        # Verify the setup was successful
        assert result is True

        # Verify client was created with correct parameters
        mock_client_class.assert_called_once_with(
            "test-api-key-123", mock_session, debug=False
        )

        # Verify login and setup_devices were called
        mock_client.login.assert_awaited_once()
        mock_client.setup_devices.assert_awaited_once()

        # Verify first refresh was called
        mock_coordinator.async_config_entry_first_refresh.assert_awaited_once()

        # Verify runtime data was set
        assert config_entry.runtime_data == mock_coordinator

        # Verify platforms were set up
        mock_forward_entry_setups.assert_awaited_once_with(config_entry, PLATFORMS)


@pytest.mark.asyncio
async def test_async_setup_entry_unauthorized_error_on_login(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Test setup with invalid API credentials (UnauthorizedError on login)."""
    config_entry = create_mock_config_entry()

    # Simulate UnauthorizedError on login
    mock_client.login.side_effect = UnauthorizedError("Invalid API key")

    with (
        patch("homeassistant.components.uhoo.Client", return_value=mock_client),
        patch(
            "homeassistant.components.uhoo.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        # Should raise ConfigEntryError
        with pytest.raises(ConfigEntryError) as exc_info:
            await async_setup_entry(hass, config_entry)

        assert "Invalid API credentials" in str(exc_info.value)

        # Verify login was attempted
        mock_client.login.assert_awaited_once()

        # Verify setup_devices was NOT called
        mock_client.setup_devices.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_entry_unauthorized_error_on_setup_devices(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Test setup with UnauthorizedError during setup_devices."""
    config_entry = create_mock_config_entry()

    # Login succeeds but setup_devices fails with UnauthorizedError
    mock_client.login.return_value = None
    mock_client.setup_devices.side_effect = UnauthorizedError("Token expired")

    with (
        patch("homeassistant.components.uhoo.Client", return_value=mock_client),
        patch(
            "homeassistant.components.uhoo.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        # Should raise ConfigEntryError
        with pytest.raises(ConfigEntryError) as exc_info:
            await async_setup_entry(hass, config_entry)

        assert "Invalid API credentials" in str(exc_info.value)

        # Verify both methods were called
        mock_client.login.assert_awaited_once()
        mock_client.setup_devices.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_setup_entry_connection_error_on_login(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Test setup with ClientConnectionError during login."""
    config_entry = create_mock_config_entry()

    # Simulate ClientConnectionError on login
    mock_client.login.side_effect = ClientConnectionError("Connection failed")

    with (
        patch("homeassistant.components.uhoo.Client", return_value=mock_client),
        patch(
            "homeassistant.components.uhoo.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        # Should raise ConfigEntryNotReady
        with pytest.raises(ConfigEntryNotReady) as exc_info:
            await async_setup_entry(hass, config_entry)

        assert "Cannot connect to uHoo servers" in str(exc_info.value)

        # Verify login was attempted
        mock_client.login.assert_awaited_once()

        # Verify setup_devices was NOT called
        mock_client.setup_devices.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_entry_dns_error_on_login(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Test setup with DNSError during login."""
    config_entry = create_mock_config_entry()

    # Simulate DNSError on login
    mock_client.login.side_effect = DNSError("DNS resolution failed")

    with (
        patch("homeassistant.components.uhoo.Client", return_value=mock_client),
        patch(
            "homeassistant.components.uhoo.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        # Should raise ConfigEntryNotReady
        with pytest.raises(ConfigEntryNotReady) as exc_info:
            await async_setup_entry(hass, config_entry)

        assert "Cannot connect to uHoo servers" in str(exc_info.value)

        # Verify login was attempted
        mock_client.login.assert_awaited_once()

        # Verify setup_devices was NOT called
        mock_client.setup_devices.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_entry_uhoo_error_on_login(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Test setup with UhooError during login."""
    config_entry = create_mock_config_entry()

    # Simulate UhooError on login
    mock_client.login.side_effect = UhooError("Some uhoo error")

    with (
        patch("homeassistant.components.uhoo.Client", return_value=mock_client),
        patch(
            "homeassistant.components.uhoo.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        # Should raise ConfigEntryNotReady
        with pytest.raises(ConfigEntryNotReady) as exc_info:
            await async_setup_entry(hass, config_entry)

        assert "Some uhoo error" in str(exc_info.value)

        # Verify login was attempted
        mock_client.login.assert_awaited_once()

        # Verify setup_devices was NOT called
        mock_client.setup_devices.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_entry_coordinator_first_refresh_fails(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_coordinator: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Test setup where coordinator's first refresh fails."""
    config_entry = create_mock_config_entry()

    # Mock the hass.config_entries methods
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    # Simulate successful client setup but coordinator refresh fails
    mock_coordinator.async_config_entry_first_refresh.side_effect = Exception(
        "First refresh failed"
    )

    with (
        patch("homeassistant.components.uhoo.Client", return_value=mock_client),
        patch(
            "homeassistant.components.uhoo.UhooDataUpdateCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.uhoo.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        # Should propagate the exception
        with pytest.raises(Exception) as exc_info:
            await async_setup_entry(hass, config_entry)

        assert "First refresh failed" in str(exc_info.value)

        # Verify client setup was completed
        mock_client.login.assert_awaited_once()
        mock_client.setup_devices.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_setup_entry_platform_setup_error(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_coordinator: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Test setup where platform setup fails."""
    config_entry = create_mock_config_entry()

    # Mock the hass.config_entries methods
    mock_forward_entry_setups = AsyncMock(
        side_effect=Exception("Platform setup failed")
    )
    hass.config_entries.async_forward_entry_setups = mock_forward_entry_setups

    with (
        patch("homeassistant.components.uhoo.Client", return_value=mock_client),
        patch(
            "homeassistant.components.uhoo.UhooDataUpdateCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.uhoo.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        # Should propagate the exception
        with pytest.raises(Exception) as exc_info:
            await async_setup_entry(hass, config_entry)

        assert "Platform setup failed" in str(exc_info.value)

        # Verify client and coordinator setup was completed
        mock_client.login.assert_awaited_once()
        mock_client.setup_devices.assert_awaited_once()
        mock_coordinator.async_config_entry_first_refresh.assert_awaited_once()


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_async_setup_entry_missing_api_key(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_coordinator: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Test setup when API key is missing from config entry data."""
    # Create config entry without API key
    config_entry = create_mock_config_entry(data={})

    with (
        patch("homeassistant.components.uhoo.Client", return_value=mock_client),
        patch(
            "homeassistant.components.uhoo.UhooDataUpdateCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.uhoo.async_get_clientsession",
            return_value=mock_session,
        ),
        pytest.raises(KeyError),
    ):
        await async_setup_entry(hass, config_entry)


@pytest.mark.asyncio
async def test_async_setup_entry_client_creation_fails(
    hass: HomeAssistant,
    mock_session: MagicMock,
) -> None:
    """Test setup when Client creation fails."""
    config_entry = create_mock_config_entry()

    with (
        patch(
            "homeassistant.components.uhoo.Client",
            side_effect=Exception("Client creation failed"),
        ),
        patch(
            "homeassistant.components.uhoo.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        # Should propagate the exception
        with pytest.raises(Exception) as exc_info:
            await async_setup_entry(hass, config_entry)

        assert "Client creation failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_async_setup_entry_coordinator_creation_fails(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Test setup when coordinator creation fails."""
    config_entry = create_mock_config_entry()

    with (
        patch("homeassistant.components.uhoo.Client", return_value=mock_client),
        patch(
            "homeassistant.components.uhoo.UhooDataUpdateCoordinator",
            side_effect=Exception("Coordinator creation failed"),
        ),
        patch(
            "homeassistant.components.uhoo.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        # Should propagate the exception
        with pytest.raises(Exception) as exc_info:
            await async_setup_entry(hass, config_entry)

        assert "Coordinator creation failed" in str(exc_info.value)

        # Since coordinator creation fails before login, login should NOT be called
        mock_client.login.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_entry_with_devices(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_coordinator: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Test setup when client has devices."""
    config_entry = create_mock_config_entry()

    # Mock the hass.config_entries methods
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    # Setup mock client with devices
    mock_client.devices = {"device1": MagicMock(), "device2": MagicMock()}

    with (
        patch("homeassistant.components.uhoo.Client", return_value=mock_client),
        patch(
            "homeassistant.components.uhoo.UhooDataUpdateCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.uhoo.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        # Call the setup function
        result = await async_setup_entry(hass, config_entry)

        # Verify the setup was successful
        assert result is True

        # Verify client setup was called
        mock_client.login.assert_awaited_once()
        mock_client.setup_devices.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_setup_entry_with_empty_devices(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_coordinator: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Test setup when client has no devices."""
    config_entry = create_mock_config_entry()

    # Mock the hass.config_entries methods
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    # Setup mock client with empty devices
    mock_client.devices = {}

    with (
        patch("homeassistant.components.uhoo.Client", return_value=mock_client),
        patch(
            "homeassistant.components.uhoo.UhooDataUpdateCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.uhoo.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        # Call the setup function
        result = await async_setup_entry(hass, config_entry)

        # Verify the setup was successful
        assert result is True

        # Verify client setup was called
        mock_client.login.assert_awaited_once()
        mock_client.setup_devices.assert_awaited_once()
