"""Tests for __init__.py with coordinator."""

from unittest.mock import AsyncMock

from aiodns.error import DNSError
from aiohttp.client_exceptions import ClientConnectionError
import pytest
from uhooapi.errors import UhooError, UnauthorizedError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_uhoo_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


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
    mock_config_entry: MockConfigEntry,
    field: str,
    exc: Exception,
    state: ConfigEntryState,
) -> None:
    """Test setup failure."""
    # Set the exception on the specified field
    getattr(mock_uhoo_client, field).side_effect = exc

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state
