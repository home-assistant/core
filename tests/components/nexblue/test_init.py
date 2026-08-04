"""Tests for NexBlue integration setup."""

from unittest.mock import MagicMock

from nexblue_api import NexBlueAuthError, NexBlueConnectionError
from nexblue_api.models import TokenBundle
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test a config entry sets up coordinator and sensors."""
    assert init_integration.state is ConfigEntryState.LOADED
    mock_client.async_ensure_access_token.assert_awaited_once()
    mock_client.async_list_chargers.assert_awaited_once()
    mock_client.async_get_charger_status.assert_awaited_once()
    assert init_integration.runtime_data.coordinator.data


async def test_setup_entry_recovers_from_invalid_refresh_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test a saved password recovers an expired refresh token once."""
    mock_client.async_ensure_access_token.side_effect = NexBlueAuthError
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.async_login.assert_awaited_once()


@pytest.mark.parametrize(
    ("refresh_error", "login_error"),
    [(NexBlueAuthError, NexBlueAuthError), (NexBlueConnectionError, None)],
)
async def test_setup_entry_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    refresh_error: type[Exception],
    login_error: type[Exception] | None,
) -> None:
    """Test setup does not load when NexBlue cannot authenticate or connect."""
    mock_client.async_ensure_access_token.side_effect = refresh_error
    mock_client.async_login.side_effect = login_error
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is not ConfigEntryState.LOADED


async def test_setup_entry_fails_when_fallback_login_has_no_refresh_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test fallback login without a refresh token stops setup."""
    mock_client.async_ensure_access_token.side_effect = NexBlueAuthError
    mock_client.async_login.return_value = TokenBundle(
        access_token="access-token",
        refresh_token=None,
        expires_in=3600,
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is not ConfigEntryState.LOADED
    mock_client.async_login.assert_awaited_once()
