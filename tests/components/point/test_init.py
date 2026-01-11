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


async def test_setup_entry_with_coordinator(
    hass: HomeAssistant,
) -> None:
    """Test successful setup with coordinator initialization."""
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

    mock_auth = MagicMock()
    mock_auth.async_get_access_token = AsyncMock(return_value="mock-token")

    mock_point_session = MagicMock()
    mock_point_session.update = AsyncMock(return_value=True)
    mock_point_session.update_webhook = AsyncMock()
    mock_point_session.homes = []
    mock_point_session.devices = []

    with (
        patch(
            "homeassistant.components.point.async_get_config_entry_implementation"
        ) as mock_impl,
        patch("homeassistant.components.point.api.AsyncConfigEntryAuth") as mock_auth_class,
        patch("homeassistant.components.point.PointSession") as mock_session_class,
        patch("homeassistant.components.point.webhook.async_register"),
    ):
        mock_impl.return_value = MagicMock()
        mock_auth_class.return_value = mock_auth
        mock_session_class.return_value = mock_point_session

        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None
