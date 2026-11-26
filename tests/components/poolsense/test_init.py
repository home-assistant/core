"""Tests for the PoolSense integration setup."""

from unittest.mock import AsyncMock

from poolsense.exceptions import PoolSenseError
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_setup_invalid_auth(
    hass: HomeAssistant,
    mock_poolsense_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails with invalid credentials and starts reauth."""
    mock_poolsense_client.test_poolsense_credentials.return_value = False

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == "Invalid authentication"

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_setup_update_failed(
    hass: HomeAssistant,
    mock_poolsense_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup is retried when the first data update fails."""
    mock_poolsense_client.get_poolsense_data.side_effect = PoolSenseError(
        500, "Server error."
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()
