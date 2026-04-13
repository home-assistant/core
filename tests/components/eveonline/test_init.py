"""Test the Eve Online integration setup."""

from unittest.mock import AsyncMock

import aiohttp
from eveonline import EveOnlineError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test successful setup of a config entry."""
    assert init_integration.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "exception",
    [
        EveOnlineError("API unavailable"),
        aiohttp.ClientError("Connection reset"),
    ],
)
async def test_setup_entry_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
    exception: Exception,
) -> None:
    """Test setup failure when the primary endpoint is unavailable."""
    mock_eveonline_client.async_get_wallet_balance.side_effect = exception

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test successful unloading of a config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_optional_endpoint_error_does_not_fail_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that errors on optional endpoints don't prevent the entry from loading."""
    mock_eveonline_client.async_get_character_location.side_effect = EveOnlineError(
        "Endpoint down"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
