"""Tests for the Rainforest RAVEn component initialisation."""

import pytest

from homeassistant.components.rainforest_raven.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import create_mock_device, create_mock_entry

from tests.common import patch


@pytest.fixture
def mock_device():
    """Mock a functioning RAVEn device."""
    mock_device = create_mock_device()
    with patch(
        "homeassistant.components.rainforest_raven.coordinator.RAVEnSerialDevice",
        return_value=mock_device,
    ):
        yield mock_device


@pytest.fixture
async def mock_entry(hass: HomeAssistant, mock_device):
    """Mock a functioning RAVEn config entry."""
    mock_entry = create_mock_entry()
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    return mock_entry


async def test_load_unload_entry(hass: HomeAssistant, mock_entry):
    """Test load and unload."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
