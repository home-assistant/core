"""Test Onkyo component setup process."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from aioonkyo import Status
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import mock_discovery, setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_receiver")
async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "receiver_infos",
    [
        None,
        [],
    ],
)
async def test_initialization_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    receiver_infos,
) -> None:
    """Test initialization failure."""
    with mock_discovery(receiver_infos):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect: AsyncMock,
) -> None:
    """Test connection failure."""
    mock_connect.side_effect = OSError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_receiver")
async def test_reconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect: AsyncMock,
    read_queue: asyncio.Queue[Status | None],
) -> None:
    """Test reconnect."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_connect.reset_mock()

    assert mock_connect.call_count == 0

    read_queue.put_nowait(None)  # Simulate a disconnect
    await asyncio.sleep(0)

    assert mock_connect.call_count == 1
