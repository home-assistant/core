"""Tests for the Sony Projector setup."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_projector: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up and unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ConnectionRefusedError, id="refused"),
        pytest.param(Exception("Timeout while connecting"), id="bare_exception"),
    ],
)
async def test_setup_retry_when_unreachable(
    hass: HomeAssistant,
    mock_projector: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: Exception | type[Exception],
) -> None:
    """Test setup is retried when the projector can't be reached."""
    mock_projector.get_power.side_effect = error
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
