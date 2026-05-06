"""Tests for the RDW integration."""

from unittest.mock import MagicMock

import pytest
from vehicle import RDWConnectionError, RDWError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rdw: MagicMock,
) -> None:
    """Test the RDW configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("side_effect", [RDWConnectionError, RDWError])
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_rdw: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
) -> None:
    """Test the RDW configuration entry not ready."""
    mock_rdw.vehicle.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_rdw.vehicle.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
