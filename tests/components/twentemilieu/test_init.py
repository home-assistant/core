"""Tests for the Twente Milieu integration."""
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.twentemilieu.const import DOMAIN
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

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@patch(
    "homeassistant.components.twentemilieu.TwenteMilieu.update",
    side_effect=RuntimeError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Twente Milieu configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_twentemilieu")
async def test_update_config_entry_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the we update old config entries with an unique ID."""
    mock_config_entry.unique_id = None
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.unique_id == "12345"
