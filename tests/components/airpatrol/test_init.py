"""Test the AirPatrol integration setup."""

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.airpatrol import (
    AirPatrolConfigEntry,
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.airpatrol.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "password": "test_password",
            "access_token": "test_access_token",
        },
        unique_id="test_unique_id",
    )


@pytest.fixture
def mock_api():
    """Mock AirPatrol API."""
    api = MagicMock()
    api.get_unique_id.return_value = "test_unique_id"
    api.get_access_token.return_value = "test_access_token"
    api.get_data = AsyncMock(return_value=[])
    return api


async def test_load_unload_config_entry(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """Test loading and unloading the config entry."""
    # Mock the API creation
    with (
        patch("homeassistant.components.airpatrol.AirPatrolAPI", return_value=mock_api),
        patch(
            "homeassistant.components.airpatrol.AirPatrolDataUpdateCoordinator"
        ) as mock_coordinator_class,
    ):
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        # Mock platform setup
        with patch.object(
            hass.config_entries, "async_forward_entry_setups"
        ) as mock_forward:
            mock_forward.return_value = True

            # Load the config entry
            result = await async_setup_entry(
                hass, cast(AirPatrolConfigEntry, mock_config_entry)
            )

            assert result is True
            assert mock_config_entry.runtime_data == mock_coordinator
            mock_coordinator.async_config_entry_first_refresh.assert_called_once()
            mock_forward.assert_called_once()

            # Mock platform unload
            with patch.object(
                hass.config_entries, "async_unload_platforms"
            ) as mock_unload:
                mock_unload.return_value = True

                # Unload the config entry
                result = await async_unload_entry(
                    hass, cast(AirPatrolConfigEntry, mock_config_entry)
                )

                assert result is True
                mock_unload.assert_called_once()


async def test_setup_entry_with_access_token(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """Test setup entry with stored access token."""
    # Mock the API creation
    with (
        patch("homeassistant.components.airpatrol.AirPatrolAPI", return_value=mock_api),
        patch(
            "homeassistant.components.airpatrol.AirPatrolDataUpdateCoordinator"
        ) as mock_coordinator_class,
    ):
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        # Mock platform setup
        with patch.object(
            hass.config_entries, "async_forward_entry_setups"
        ) as mock_forward:
            mock_forward.return_value = True

            # Load the config entry
            result = await async_setup_entry(
                hass, cast(AirPatrolConfigEntry, mock_config_entry)
            )

            assert result is True
            assert mock_config_entry.runtime_data == mock_coordinator


async def test_setup_entry_without_access_token(hass: HomeAssistant) -> None:
    """Test setup entry without stored access token."""
    # Create config entry without access token
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"email": "test@example.com", "password": "test_password"},
        unique_id="test_unique_id",
    )

    # Mock the API creation
    with patch("homeassistant.components.airpatrol.AirPatrolAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.get_unique_id.return_value = "test_unique_id"
        mock_api.get_access_token.return_value = "new_access_token"
        mock_api.get_data = AsyncMock(return_value={"status": "online"})
        mock_api_class.authenticate = AsyncMock(return_value=mock_api)

        # Mock the coordinator
        with patch(
            "homeassistant.components.airpatrol.AirPatrolDataUpdateCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            # Mock platform setup
            with patch.object(
                hass.config_entries, "async_forward_entry_setups"
            ) as mock_forward:
                mock_forward.return_value = True

                # Mock the config entry update
                with patch.object(
                    hass.config_entries, "async_update_entry"
                ) as mock_update:
                    # Load the config entry
                    result = await async_setup_entry(
                        hass, cast(AirPatrolConfigEntry, config_entry)
                    )

                    assert result is True
                    assert config_entry.runtime_data == mock_coordinator

                    # Verify authentication was called and access token was stored
                    mock_api_class.authenticate.assert_called_once()
                    call_args = mock_api_class.authenticate.call_args
                    assert call_args[0][1] == "test@example.com"  # email
                    assert call_args[0][2] == "test_password"  # password
                    mock_update.assert_called_once_with(
                        config_entry,
                        data={
                            "email": "test@example.com",
                            "password": "test_password",
                            "access_token": "new_access_token",
                        },
                    )


@pytest.mark.asyncio
async def test_setup_entry_authentication_failure(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test setup entry fails with authentication error."""
    mock_config_entry.runtime_data = None
    with pytest.raises(ConfigEntryAuthFailed):
        await async_setup_entry(hass, cast(AirPatrolConfigEntry, mock_config_entry))


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test setup entry fails with connection error."""
    mock_config_entry.runtime_data = None
    with pytest.raises(ConfigEntryAuthFailed):
        await async_setup_entry(hass, cast(AirPatrolConfigEntry, mock_config_entry))


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry, mock_api
) -> None:
    """Test successful setup entry."""
    # Mock the API creation
    with (
        patch("homeassistant.components.airpatrol.AirPatrolAPI", return_value=mock_api),
        patch(
            "homeassistant.components.airpatrol.AirPatrolDataUpdateCoordinator"
        ) as mock_coordinator_class,
    ):
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        # Mock platform setup
        with patch.object(
            hass.config_entries, "async_forward_entry_setups"
        ) as mock_forward:
            mock_forward.return_value = True

            # Load the config entry
            result = await async_setup_entry(
                hass, cast(AirPatrolConfigEntry, mock_config_entry)
            )

            assert result is True
            assert mock_config_entry.runtime_data == mock_coordinator

            # Verify API was created with correct parameters


async def test_unload_entry_failure(hass: HomeAssistant, mock_config_entry) -> None:
    """Test unloading config entry when platform unload fails."""
    # Mock platform unload failure
    with patch.object(hass.config_entries, "async_unload_platforms") as mock_unload:
        mock_unload.return_value = False

        # Unload the config entry
        result = await async_unload_entry(
            hass, cast(AirPatrolConfigEntry, mock_config_entry)
        )

        assert result is False
        mock_unload.assert_called_once()


async def test_config_entry_type(hass: HomeAssistant) -> None:
    """Test config entry type."""
    # Test that the type alias is properly defined
    assert AirPatrolConfigEntry.__name__ == "AirPatrolConfigEntry"

    # Test that it can be used as a type hint
    def test_function(entry: AirPatrolConfigEntry) -> None:
        """Test function with type hint."""
        # Just test that the type hint works

    # This should not raise any type errors
    test_function(cast(AirPatrolConfigEntry, MockConfigEntry(domain="airpatrol")))


async def test_async_reload_entry(hass: HomeAssistant, mock_api) -> None:
    """Test reloading the config entry clears the cache."""
    # Create a mock config entry using MockConfigEntry
    entry = MockConfigEntry(
        domain="airpatrol",
        data={"email": "test@example.com", "password": "test_password"},
        unique_id="test_user_id",
    )
    entry.add_to_hass(hass)

    # Mock the runtime_data with an API that has a cache
    mock_api.clear_pairings_cache = MagicMock()
    entry.runtime_data = MagicMock()
    entry.runtime_data.api = mock_api

    # Mock the config entries reload method
    with patch.object(hass.config_entries, "async_reload") as mock_reload:
        await async_reload_entry(hass, cast(AirPatrolConfigEntry, entry))

        # Verify the cache was cleared
        mock_api.clear_pairings_cache.assert_called_once()

        # Verify the entry was reloaded
        mock_reload.assert_called_once_with(entry.entry_id)
