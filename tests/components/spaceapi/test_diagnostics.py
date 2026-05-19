"""Tests for SpaceAPI diagnostics."""

from __future__ import annotations

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert diag == snapshot(exclude=props("created_at", "modified_at", "entry_id"))
