"""Tests for AirLino config-entry lifecycle."""

from unittest.mock import MagicMock

from airlino_api import AirlinoApiConnectionError, AirlinoApiError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airlino_api: MagicMock,
) -> None:
    """Load and unload a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "method",
    [
        "async_get_device_info",
        "async_get_player_status",
        "async_get_master_volume",
    ],
)
@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(AirlinoApiConnectionError("offline"), id="connection_error"),
        pytest.param(AirlinoApiError("failed"), id="api_error"),
    ],
)
async def test_setup_retries_when_device_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airlino_api: MagicMock,
    method: str,
    exception: Exception,
) -> None:
    """Retry setup later when the device cannot be reached."""
    getattr(mock_airlino_api, method).side_effect = exception
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
