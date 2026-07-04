"""Tests for the Actron Air integration setup."""

from unittest.mock import AsyncMock

from actron_neo_api import ActronAirAPIError, ActronAirAuthError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry raises ConfigEntryAuthFailed on auth error."""
    mock_actron_api.get_ac_systems.side_effect = ActronAirAuthError("Auth failed")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_api_error(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry raises ConfigEntryNotReady on API error."""
    mock_actron_api.get_ac_systems.side_effect = ActronAirAPIError("API failed")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
