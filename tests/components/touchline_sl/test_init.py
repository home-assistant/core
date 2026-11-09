"""Tests for the Roth Touchline SL integration setup."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry
from pytouchlinesl.client import RothAPIError

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_touchlinesl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a 401 during setup starts a reauth flow."""
    mock_touchlinesl_client.modules.side_effect = RothAPIError(status=401)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_setup_api_error_retries(
    hass: HomeAssistant,
    mock_touchlinesl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a non-authentication API error during setup retries setup."""
    mock_touchlinesl_client.modules.side_effect = RothAPIError(status=502)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()
