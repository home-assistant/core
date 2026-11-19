"""Tests for the qBittorrent diagnostics."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize("has_torrents", [True, False])
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_qbittorrent: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    has_torrents: bool,
) -> None:
    """Test diagnostics."""
    if not has_torrents:
        del mock_qbittorrent.sync_maindata.return_value["torrents"]

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
