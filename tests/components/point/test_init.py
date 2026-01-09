"""Tests for the Point component."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.point import DOMAIN
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
    from homeassistant.components.point.coordinator import PointDataUpdateCoordinator

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
