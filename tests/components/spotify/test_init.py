"""Tests for the Spotify initialization."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from spotifyaio import SpotifyConnectionError, SpotifyForbiddenError

from homeassistant.components.spotify.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

TOKEN_URL = "https://accounts.spotify.com/api/token"


@pytest.mark.usefixtures("setup_credentials")
async def test_setup(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify setup."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("setup_credentials")
@pytest.mark.parametrize(
    "method",
    [
        "get_current_user",
        "get_devices",
    ],
)
async def test_setup_with_required_calls_failing(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    method: str,
) -> None:
    """Test the Spotify setup with required calls failing."""
    getattr(mock_spotify.return_value, method).side_effect = SpotifyConnectionError
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_free_account_is_failing(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the Spotify setup with a free account is failing."""
    mock_spotify.return_value.get_current_user.side_effect = SpotifyForbiddenError(
        "Check settings on developer.spotify.com/dashboard,"
        " the user may not be registered."
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    issue = issue_registry.issues.get(
        (DOMAIN, f"user_not_premium_{mock_config_entry.unique_id}")
    )
    assert issue, "Repair issue not created"


@pytest.mark.usefixtures("setup_credentials")
async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.spotify.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("setup_credentials", "mock_spotify")
@pytest.mark.parametrize("expires_at", [0], ids=["expired"])
async def test_revoked_refresh_token_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a revoked refresh token asks the user to reauthenticate.

    Setup maps the failure onto ConfigEntryNotReady, so without starting reauth
    the entry would keep retrying a token that can never be refreshed again.
    """
    aioclient_mock.post(TOKEN_URL, status=HTTPStatus.BAD_REQUEST, json={})
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["handler"] == DOMAIN
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
