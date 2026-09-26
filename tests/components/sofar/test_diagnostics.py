"""Tests for the Sofar diagnostics."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusConnectionError, ModbusError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

from homeassistant.components.sofar.const import SETTINGS_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed
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

    assert diag == snapshot(
        matcher=path_type(
            {r"^link\.stats\.(median|p95|slowest)$": (float,)}, regex=True
        )
    )


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


async def test_diagnostics_decodes_address_masks(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a mask is assembled from four registers, most significant first."""
    holding = mock_connection.for_unit(1).holding
    holding[0x0400] = 0x0001
    holding[0x0401] = 0x0002
    holding[0x0402] = 0x0003
    holding[0x0403] = 0x0004

    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag["address_masks"]["1024"] == 0x0001000200030004


@pytest.mark.parametrize(
    ("error", "error_name"),
    [
        pytest.param(ModbusTimeoutError("silent"), "ModbusTimeoutError", id="timeout"),
        pytest.param(
            ModbusConnectionError("gone"), "ModbusConnectionError", id="link_lost"
        ),
    ],
)
async def test_diagnostics_inverter_unreachable(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    error: ModbusError,
    error_name: str,
) -> None:
    """Test diagnostics still download when the inverter stops answering."""
    mock_connection.for_unit(1).fail_requests(error)
    freezer.tick(timedelta(seconds=SETTINGS_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag["read_error"] == error_name
    assert diag["raw"] is None
    assert diag["address_masks"] is None
    assert diag["coordinator_errors"] == {
        "readings": error_name,
        "settings": error_name,
    }
