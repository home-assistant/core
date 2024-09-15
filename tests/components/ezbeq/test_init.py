"""Tests for the ezbeq Profile Loader integration setup."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.ezbeq.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

from tests.common import MockConfigEntry

pytestmark = pytest.mark.asyncio


async def test_setup_unload_and_reload_entry(
    hass: HomeAssistant,
    mock_ezbeq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entry setup and unload."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state == ConfigEntryState.LOADED


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_ezbeq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
