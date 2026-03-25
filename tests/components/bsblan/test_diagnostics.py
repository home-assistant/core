"""Tests for the diagnostics data provided by the BSBLan integration."""

from unittest.mock import AsyncMock

from bsblan import BSBLANError
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics_data = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert diagnostics_data == snapshot


async def test_diagnostics_without_static_values(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics when static values are not available."""
    mock_bsblan.static_values.side_effect = BSBLANError("General error")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics_data = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert "info" in diagnostics_data
    assert "device" in diagnostics_data
    assert "fast_coordinator_data" in diagnostics_data
    assert diagnostics_data["static"] is None
