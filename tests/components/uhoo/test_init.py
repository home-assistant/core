"""Tests for __init__.py with coordinator."""

from unittest.mock import AsyncMock

from aiodns.error import DNSError
from aiohttp.client_exceptions import ClientConnectionError
import pytest
from uhooapi.errors import UhooError, UnauthorizedError

from homeassistant.components.uhoo import async_unload_entry
from homeassistant.components.uhoo.const import PLATFORMS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_uhoo_config


async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_uhoo_client, mock_uhoo_config_entry
) -> None:
    """Test successful setup of a uHoo config entry."""
    await setup_uhoo_config(hass, mock_uhoo_config_entry)

    assert mock_uhoo_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "field",
    [
        "login",
        "setup_devices",
    ],
)
@pytest.mark.parametrize(
    ("exc", "state"),
    [
        (ClientConnectionError, ConfigEntryState.SETUP_RETRY),
        (DNSError, ConfigEntryState.SETUP_RETRY),
        (UhooError, ConfigEntryState.SETUP_RETRY),
        (UnauthorizedError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_uhoo_client: AsyncMock,
    mock_uhoo_config_entry,
    field: str,
    exc: Exception,
    state: ConfigEntryState,
) -> None:
    """Test setup failure."""
    # Set the exception on the specified field
    getattr(mock_uhoo_client, field).side_effect = exc

    await setup_uhoo_config(hass, mock_uhoo_config_entry)

    assert mock_uhoo_config_entry.state is state


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_uhoo_client: AsyncMock,
    mock_uhoo_config_entry,
) -> None:
    """Test load and unload entry."""
    await setup_uhoo_config(hass, mock_uhoo_config_entry)

    assert mock_uhoo_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_uhoo_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_uhoo_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_async_unload_entry_failure(
    hass: HomeAssistant, mock_uhoo_config_entry
) -> None:
    """Test failed unloading of a config entry."""

    # Mock the hass.config_entries methods
    mock_unload_platforms = AsyncMock(return_value=False)
    hass.config_entries.async_unload_platforms = mock_unload_platforms

    # Call the unload function
    result = await async_unload_entry(hass, mock_uhoo_config_entry)

    # Verify the unload failed
    assert result is False

    # Verify async_unload_platforms was called with correct parameters
    mock_unload_platforms.assert_awaited_once_with(mock_uhoo_config_entry, PLATFORMS)
