"""Tests for the CentriConnect/MyPropane configuration initialization."""

from unittest.mock import AsyncMock

from aiocentriconnect.exceptions import CentriConnectConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_centriconnect_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry not ready."""
    mock_centriconnect_client.async_get_tank_data.side_effect = (
        CentriConnectConnectionError
    )
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_centriconnect_client.async_get_tank_data.side_effect = None
