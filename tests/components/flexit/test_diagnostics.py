"""Tests for Flexit diagnostics."""

from modbus_connection.mock import MockModbusUnit
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    mock_modbus_unit.holding.update({8: 215, 17: 2})
    mock_modbus_unit.input.update(
        {9: 200, 11: 50, 8: 120, 14: 0, 15: 0, 13: 0, 27: 0, 28: 0, 48: 0}
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
