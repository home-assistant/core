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
                "homeassistant.components.unraid.async_get_clientsession"
            ) as mock_session,
        ):
            MockAPIClient.return_value = _create_mock_api_client()
            MockSystemCoord.return_value = _create_mock_coordinator()
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
            mock_api.get_server_info = AsyncMock(
                side_effect=UnraidAuthenticationError("Invalid API key")
            )
            MockAPIClient.return_value = mock_api
            mock_session.return_value = MagicMock()

            with pytest.raises(ConfigEntryAuthFailed):
                await async_setup_entry(hass, entry)

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
            mock_api.get_server_info = AsyncMock(
                side_effect=UnraidConnectionError("Connection refused")
            )
            MockAPIClient.return_value = mock_api
            mock_session.return_value = MagicMock()

            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(hass, entry)


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
        entry.runtime_data = UnraidRuntimeData(
            system_coordinator=MagicMock(),
            server_info=_create_mock_server_info(uuid="test-uuid", hostname="tower"),
        )

        with patch.object(
            hass.config_entries,
            "async_unload_platforms",
            return_value=True,
        ):
            result = await async_unload_entry(hass, entry)

        assert result is True


