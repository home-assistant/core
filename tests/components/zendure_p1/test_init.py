"""Tests for the Zendure Smart Meter P1 init module."""

from unittest.mock import AsyncMock

import pytest
from zendure_p1 import (
    ZendureP1ConnectionError,
    ZendureP1ResponseError,
    ZendureP1TimeoutError,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zendure_p1_client: AsyncMock,
) -> None:
    """Test load and unload of the config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_zendure_p1_client.close.assert_awaited_once()


@pytest.mark.parametrize(
    "side_effect",
    [
        ZendureP1ConnectionError,
        ZendureP1TimeoutError,
        ZendureP1ResponseError,
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zendure_p1_client: AsyncMock,
    side_effect: type[Exception],
) -> None:
    """Test that a failed first refresh puts the entry in SETUP_RETRY state."""
    mock_zendure_p1_client.get_report.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_zendure_p1_client.close.assert_awaited_once()
