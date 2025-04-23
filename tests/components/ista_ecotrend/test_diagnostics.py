"""Tests for ista EcoTrend diagnostics platform ."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("mock_ista")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ista_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    ista_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(ista_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, ista_config_entry)
        == snapshot
    )
