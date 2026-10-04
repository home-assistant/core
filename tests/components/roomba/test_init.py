"""Tests for the Roomba integration setup."""

from unittest.mock import AsyncMock

import pytest
from roombapy import RoombaAuthError, RoombaConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(RoombaConnectionError, id="unreachable"),
        pytest.param(RoombaAuthError, id="rejected_password"),
    ],
)
async def test_setup_retry_on_connect_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
    error: type[Exception],
) -> None:
    """Test that a failed connection schedules a retry."""
    mock_roomba.connect.side_effect = error

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_disconnects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
) -> None:
    """Test that unloading the entry closes the connection."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_roomba.connect.assert_awaited_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_roomba.disconnect.assert_awaited_once()


async def test_stop_disconnects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
) -> None:
    """Test that stopping Home Assistant closes the connection."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_roomba.disconnect.assert_awaited_once()
