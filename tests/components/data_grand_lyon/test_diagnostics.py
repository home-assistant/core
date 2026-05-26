"""Tests for the Data Grand Lyon diagnostics."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == snapshot(exclude=props("created_at", "modified_at", "entry_id", "subentry_id"))


async def test_config_entry_diagnostics_with_velov(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_velov_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics with Vélo'v data."""
    mock_velov_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_velov_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_velov_config_entry
    ) == snapshot(exclude=props("created_at", "modified_at", "entry_id", "subentry_id"))
