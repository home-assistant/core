"""Test the Sofar Inverter Modbus diagnostics."""

from unittest.mock import patch

from modbus_connection.mock import MockModbusConnection
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag == snapshot


async def test_diagnostics_includes_active_faults(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test active faults are decoded by name in the diagnostics dump."""
    mock_connection.for_unit(1).holding[0x0405] = 0b1  # ID001_GRID_OVER_VOLTAGE

    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert diag["active_faults"] == ["grid_over_voltage"]


async def test_diagnostics_redacts_serial_number(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test the serial number is redacted, both as a field and as raw ASCII."""
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag["serial_number"] == "**REDACTED**"
    holding = diag["raw"]["holding"]
    for address in range(0x0445, 0x044C):
        assert str(address) not in holding
