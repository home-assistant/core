"""Tests for satel integra diagnostics."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    hass_client: ClientSessionGenerator,
    mock_config_entry_with_subentries: MockConfigEntry,
    mock_satel: AsyncMock,
) -> None:
    """Test diagnostics for config entry."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry_with_subentries
    )
    assert diagnostics == snapshot(exclude=props("created_at", "modified_at", "id"))
