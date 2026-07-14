"""Tests for the Gatus integration setup and unload lifecycle."""

from unittest.mock import AsyncMock

from gatus_api import GatusClientError
import pytest

from homeassistant.components.gatus.coordinator import GatusDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_gatus_client")
async def test_setup_and_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test standard successful setup and unload cycle of the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert isinstance(mock_config_entry.runtime_data, GatusDataUpdateCoordinator)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_failure_retry(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an API connection failure during initial setup places the entry in retry state."""
    mock_gatus_client.get_endpoints_statuses.side_effect = GatusClientError(
        "Cannot connect to Gatus API during initial setup"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
