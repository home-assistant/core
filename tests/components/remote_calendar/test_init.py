"""Tests for init platform of Remote Calendar."""

from unittest.mock import AsyncMock
from httpx import ConnectError, HTTPStatusError, UnsupportedProtocol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import pytest
from . import setup_integration
from .conftest import TEST_ENTITY
from homeassistant.components.remote_calendar.const import DOMAIN
from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_httpx_client: AsyncMock
) -> None:
    """Test loading and unloading a config entry."""
    await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "off"

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception"),
    [
        (ValueError),
        (ConnectError),
        (HTTPStatusError),
        (UnsupportedProtocol),
    ],
)
async def test_update_failed(
    hass: HomeAssistant,
    mock_httpx_client: AsyncMock,
    config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test update failed."""
    mock_httpx_client.get.side_effect = exception
    await setup_integration(hass, config_entry)
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
