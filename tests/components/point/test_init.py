"""Tests for the Point component."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.point import DOMAIN
from homeassistant.components.point.coordinator import PointDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from tests.common import MockConfigEntry


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
            },
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.point.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_receives_config_entry(
    hass: HomeAssistant,
) -> None:
    """Test that coordinator is initialized with config_entry parameter."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
            },
        },
    )

    mock_point_session = MagicMock()

    # Initialize coordinator with config_entry parameter
    coordinator = PointDataUpdateCoordinator(hass, mock_point_session, config_entry)

    # Verify that config_entry was properly passed and stored
    assert coordinator.config_entry == config_entry


async def test_setup_entry_passes_config_entry_to_coordinator(
    hass: HomeAssistant,
) -> None:
    """Test that async_setup_entry passes config_entry to coordinator."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
            },
            "webhook_id": "test_webhook_id",
        },
    )
    config_entry.add_to_hass(hass)

    mock_coordinator_init = MagicMock(return_value=None)

    with (
        patch(
            "homeassistant.components.point.async_get_config_entry_implementation"
        ) as mock_get_impl,
        patch("homeassistant.components.point.OAuth2Session"),
        patch(
            "homeassistant.components.point.api.AsyncConfigEntryAuth.async_get_access_token",
            return_value="mock_token",
        ),
        patch("homeassistant.components.point.PointSession") as mock_session,
        patch(
            "homeassistant.components.point.PointDataUpdateCoordinator.__init__",
            mock_coordinator_init,
        ) as mock_coord_init,
        patch(
            "homeassistant.components.point.PointDataUpdateCoordinator.async_config_entry_first_refresh",
            new_callable=AsyncMock,
        ),
        patch("homeassistant.components.point.webhook.async_generate_url"),
        patch("homeassistant.components.point.webhook.async_register"),
    ):
        mock_get_impl.return_value = MagicMock()
        mock_session.return_value.update_webhook = AsyncMock()

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify coordinator was initialized with config_entry as third argument
        mock_coord_init.assert_called_once()
        call_args = mock_coord_init.call_args[0]
        assert len(call_args) == 3
        assert call_args[2] == config_entry
