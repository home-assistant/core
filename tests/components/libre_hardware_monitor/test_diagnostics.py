"""Tests for Libre Hardware Monitor diagnostics."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_auth_config_entry: MockConfigEntry,
    mock_lhm_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    mock_auth_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_auth_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        await get_diagnostics_for_config_entry(
            hass, hass_client, mock_auth_config_entry
        )
        == snapshot
    )
