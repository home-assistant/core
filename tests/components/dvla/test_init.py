"""Test the DVLA integration setup."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock

from aio_dvla_vehicle_enquiry import DVLAError
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_entry(
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
    mock_dvla_client: AsyncMock,
) -> None:
    """Test setting up a config entry."""
    entry = await setup_dvla_entry()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None
    assert entry.runtime_data.reg_number == "AB12CDE"
    mock_dvla_client.assert_awaited_once_with("AB12CDE")


async def test_unload_entry(
    hass: HomeAssistant,
    setup_dvla_entry: Callable[
        [dict[str, Any] | None],
        Awaitable[MockConfigEntry],
    ],
) -> None:
    """Test unloading a config entry."""
    entry = await setup_dvla_entry()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_retries_on_dvla_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dvla_client: AsyncMock,
) -> None:
    """Test setup retries when DVLA update fails."""
    mock_config_entry.add_to_hass(hass)
    mock_dvla_client.side_effect = DVLAError("DVLA unavailable")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
