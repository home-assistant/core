"""Tests for the Twente Milieu integration."""

from unittest.mock import MagicMock

import pytest
from twentemilieu import TwenteMilieuConnectionError, TwenteMilieuError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_twentemilieu")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Twente Milieu configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "side_effect", [TwenteMilieuConnectionError, TwenteMilieuError]
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_twentemilieu: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
) -> None:
    """Test the Twente Milieu configuration entry not ready."""
    mock_twentemilieu.update.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_twentemilieu.update.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
