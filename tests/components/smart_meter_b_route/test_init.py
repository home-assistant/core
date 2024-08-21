"""Tests for the Smart Meter B Route integration init."""

from unittest.mock import patch

from momonga import MomongaError, MomongaKeyError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_async_setup_entry_success(hass: HomeAssistant, mock_momonga) -> None:
    """Test successful setup of entry."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("error"),
    [
        (MomongaError),
        (MomongaKeyError),
    ],
)
async def test_async_setup_entry_error(
    hass: HomeAssistant, error: Exception, mock_momonga
) -> None:
    """Test successful setup of entry."""
    with patch.object(mock_momonga, "get_instantaneous_current", side_effect=error):
        entry = configure_integration(hass)
        assert entry.state is ConfigEntryState.NOT_LOADED
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert [flow.get("step_id") for flow in flows] == []
