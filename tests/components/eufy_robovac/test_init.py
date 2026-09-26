"""Tests for Eufy RoboVac setup."""

from unittest.mock import AsyncMock, patch

from eufy_robovac import RoboVacConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_robovac: AsyncMock,
) -> None:
    """Test setup performs an initial update and can unload."""
    await init_integration(hass, mock_config_entry, mock_robovac)

    assert mock_config_entry.runtime_data.client is mock_robovac
    mock_robovac.update.assert_awaited_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_vacuum_is_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_robovac: AsyncMock,
) -> None:
    """Test setup retries when the first local update fails."""
    mock_robovac.update.side_effect = RoboVacConnectionError("unreachable")
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.eufy_robovac.RoboVac",
        return_value=mock_robovac,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
