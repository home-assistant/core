"""Tests for the Homecast integration init."""

from unittest.mock import AsyncMock, patch

from pyhomecast import HomecastAuthError, HomecastConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.coordinator is not None


async def test_unload_entry(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries on connection error."""
    mock_homecast.get_state.side_effect = HomecastConnectionError("timeout")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup triggers reauth on auth error from coordinator."""
    mock_homecast.get_state.side_effect = HomecastAuthError("unauthorized")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_token_refresh_reauth(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup triggers reauth when OAuth token refresh fails."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=OAuth2TokenRequestReauthError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_token_refresh_error(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails when OAuth token request fails."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=OAuth2TokenRequestError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
