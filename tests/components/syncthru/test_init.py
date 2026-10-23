"""Tests for the syncthru integration setup."""

from unittest.mock import AsyncMock, patch

from pysyncthru import SyncThruAPINotSupported

from homeassistant.components.syncthru.coordinator import SyncthruCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_api_not_supported(
    hass: HomeAssistant,
    mock_syncthru: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails when the printer does not support the JSON API."""

    async def _first_refresh(coordinator: SyncthruCoordinator) -> None:
        coordinator.last_exception = SyncThruAPINotSupported()

    with patch.object(
        SyncthruCoordinator,
        "async_config_entry_first_refresh",
        autospec=True,
        side_effect=_first_refresh,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert (
        mock_config_entry.reason == "The printer does not support the SyncThru JSON API"
    )
