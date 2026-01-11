"""Tests for Unraid integration setup and teardown."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from unraid_api.exceptions import UnraidAuthenticationError, UnraidConnectionError
from unraid_api.models import ServerInfo

from homeassistant.components.unraid import (
    PLATFORMS,
    UnraidRuntimeData,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.unraid.const import DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from . import _create_mock_server_info

from tests.common import MockConfigEntry


def _create_mock_api_client(
    server_info: ServerInfo | None = None,
) -> AsyncMock:
    """Create a mock API client with standard responses."""
    mock_api = AsyncMock()
    mock_api.test_connection = AsyncMock(return_value=True)
    mock_api.get_server_info = AsyncMock(
        return_value=server_info or _create_mock_server_info()
    )
    mock_api.close = AsyncMock()
    return mock_api


def _create_mock_coordinator() -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data = {}
    return coordinator


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    async def test_successful_setup(self, hass: HomeAssistant) -> None:
        """Test successful integration setup."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={
                CONF_HOST: "192.168.1.100",
                CONF_API_KEY: "test-api-key",
                CONF_PORT: 443,
                CONF_VERIFY_SSL: True,
            },
            unique_id="test-uuid-123",
        )
        entry.add_to_hass(hass)

        with (
            patch("homeassistant.components.unraid.UnraidClient") as MockAPIClient,
            patch(
                "homeassistant.components.unraid.UnraidSystemCoordinator"
            ) as MockSystemCoord,
            patch(
                "homeassistant.components.unraid.UnraidStorageCoordinator"
            ) as MockStorageCoord,
            patch(
                "homeassistant.components.unraid.async_get_clientsession"
            ) as mock_session,
        ):
            MockAPIClient.return_value = _create_mock_api_client()
            MockSystemCoord.return_value = _create_mock_coordinator()
            MockStorageCoord.return_value = _create_mock_coordinator()
            mock_session.return_value = MagicMock()

            # Mock platform setup
            with patch.object(
                hass.config_entries, "async_forward_entry_setups", return_value=None
            ):
                result = await async_setup_entry(hass, entry)

        assert result is True
        assert entry.runtime_data is not None
        assert isinstance(entry.runtime_data, UnraidRuntimeData)
        assert entry.runtime_data.server_info.uuid == "test-uuid-123"
        assert entry.runtime_data.server_info.hostname == "tower"

    async def test_setup_with_auth_error(self, hass: HomeAssistant) -> None:
        """Test setup fails with authentication error."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={
                CONF_HOST: "192.168.1.100",
                CONF_API_KEY: "invalid-key",
            },
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        with (
            patch("homeassistant.components.unraid.UnraidClient") as MockAPIClient,
            patch(
                "homeassistant.components.unraid.async_get_clientsession"
            ) as mock_session,
        ):
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=UnraidAuthenticationError("Invalid API key")
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api
            mock_session.return_value = MagicMock()

            with pytest.raises(ConfigEntryAuthFailed):
                await async_setup_entry(hass, entry)

            # API client should be closed on error
            mock_api.close.assert_called_once()

    async def test_setup_with_connection_error(self, hass: HomeAssistant) -> None:
        """Test setup fails with connection error."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={
                CONF_HOST: "192.168.1.100",
                CONF_API_KEY: "test-key",
            },
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        with (
            patch("homeassistant.components.unraid.UnraidClient") as MockAPIClient,
            patch(
                "homeassistant.components.unraid.async_get_clientsession"
            ) as mock_session,
        ):
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=UnraidConnectionError("Connection refused")
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api
            mock_session.return_value = MagicMock()

            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(hass, entry)

    async def test_setup_uses_baseboard_fallback(self, hass: HomeAssistant) -> None:
        """Test setup captures baseboard info for hw_manufacturer/hw_model."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={
                CONF_HOST: "192.168.1.100",
                CONF_API_KEY: "test-api-key",
            },
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        # Create mock API with baseboard fallback in ServerInfo
        server_info = _create_mock_server_info(
            uuid="test-uuid",
            hostname="tower",
            hw_manufacturer="Supermicro",
            hw_model="X11SSH-F",
        )
        mock_api = _create_mock_api_client(server_info=server_info)

        with (
            patch("homeassistant.components.unraid.UnraidClient") as MockAPIClient,
            patch(
                "homeassistant.components.unraid.UnraidSystemCoordinator"
            ) as MockSystemCoord,
            patch(
                "homeassistant.components.unraid.UnraidStorageCoordinator"
            ) as MockStorageCoord,
            patch(
                "homeassistant.components.unraid.async_get_clientsession"
            ) as mock_session,
        ):
            MockAPIClient.return_value = mock_api
            MockSystemCoord.return_value = _create_mock_coordinator()
            MockStorageCoord.return_value = _create_mock_coordinator()
            mock_session.return_value = MagicMock()

            with patch.object(
                hass.config_entries, "async_forward_entry_setups", return_value=None
            ):
                await async_setup_entry(hass, entry)

        # DeviceInfo should show Lime Technology and Unraid version
        assert entry.runtime_data.server_info.manufacturer == "Lime Technology"
        assert entry.runtime_data.server_info.sw_version == "7.2.0"
        # Hardware info should be captured from baseboard fallback
        assert entry.runtime_data.server_info.hw_manufacturer == "Supermicro"
        assert entry.runtime_data.server_info.hw_model == "X11SSH-F"

    async def test_setup_with_default_options(self, hass: HomeAssistant) -> None:
        """Test setup uses default polling intervals when options not set."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={
                CONF_HOST: "192.168.1.100",
                CONF_API_KEY: "test-api-key",
            },
            options={},  # No options set
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        with (
            patch("homeassistant.components.unraid.UnraidClient") as MockAPIClient,
            patch(
                "homeassistant.components.unraid.UnraidSystemCoordinator"
            ) as MockSystemCoord,
            patch(
                "homeassistant.components.unraid.UnraidStorageCoordinator"
            ) as MockStorageCoord,
            patch(
                "homeassistant.components.unraid.async_get_clientsession"
            ) as mock_session,
        ):
            MockAPIClient.return_value = _create_mock_api_client()
            mock_system = _create_mock_coordinator()
            mock_storage = _create_mock_coordinator()
            MockSystemCoord.return_value = mock_system
            MockStorageCoord.return_value = mock_storage
            mock_session.return_value = MagicMock()

            with patch.object(
                hass.config_entries, "async_forward_entry_setups", return_value=None
            ):
                await async_setup_entry(hass, entry)

        # Verify coordinators were created with default intervals
        MockSystemCoord.assert_called_once()
        MockStorageCoord.assert_called_once()


class TestAsyncUnloadEntry:
    """Test async_unload_entry function."""

    async def test_successful_unload(self, hass: HomeAssistant) -> None:
        """Test successful integration unload."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={
                CONF_HOST: "192.168.1.100",
                CONF_API_KEY: "test-api-key",
            },
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        # Setup mock runtime data
        mock_api = AsyncMock()
        mock_api.close = AsyncMock()
        entry.runtime_data = UnraidRuntimeData(
            api_client=mock_api,
            system_coordinator=MagicMock(),
            storage_coordinator=MagicMock(),
            server_info=_create_mock_server_info(uuid="test-uuid", hostname="tower"),
        )

        with patch.object(
            hass.config_entries,
            "async_unload_platforms",
            return_value=True,
        ):
            result = await async_unload_entry(hass, entry)

        assert result is True
        mock_api.close.assert_called_once()

    async def test_unload_with_platform_failure(self, hass: HomeAssistant) -> None:
        """Test unload when platform unload fails."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={
                CONF_HOST: "192.168.1.100",
                CONF_API_KEY: "test-api-key",
            },
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        mock_api = AsyncMock()
        mock_api.close = AsyncMock()
        entry.runtime_data = UnraidRuntimeData(
            api_client=mock_api,
            system_coordinator=MagicMock(),
            storage_coordinator=MagicMock(),
            server_info=_create_mock_server_info(),
        )

        with patch.object(
            hass.config_entries,
            "async_unload_platforms",
            return_value=False,
        ):
            result = await async_unload_entry(hass, entry)

        assert result is False
        # API client should NOT be closed if platform unload fails
        mock_api.close.assert_not_called()


class TestPlatforms:
    """Test platform constants."""

    def test_platforms_list(self) -> None:
        """Test that all expected platforms are defined."""

        assert Platform.SENSOR in PLATFORMS
        assert len(PLATFORMS) == 1
