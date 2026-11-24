"""Tests for the BLUETTI Modbus diagnostics."""

from unittest.mock import AsyncMock, patch

from bluetti_modbus_lib import Balco260
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration

# Registers 50206, 51206 and 53007 hold the serials of the device, its battery
# pack and its IoT module, four registers each.
SERIAL_ADDRESSES = [
    base + offset for base in (50206, 51206, 53007) for offset in range(4)
]


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    await setup_integration(hass, mock_config_entry)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert diag == snapshot


async def test_diagnostics_leave_out_serial_registers(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no register holding a serial number is in the raw dump."""
    await setup_integration(hass, mock_config_entry)

    # The read plan covers only the device serial, so the raw read is mocked
    # to return all three ranges and their neighbours.
    raw = {"holding": dict.fromkeys(SERIAL_ADDRESSES, 1)}
    raw["holding"] |= {50205: 1, 50210: 1, 51205: 1, 51210: 1, 53006: 1, 53011: 1}
    with patch.object(Balco260, "async_read_raw", AsyncMock(return_value=raw)):
        diag = await get_diagnostics_for_config_entry(
            hass, hass_client, mock_config_entry
        )

    assert diag["values"]["d_serial"] == "**REDACTED**"
    assert sorted(diag["raw"]["holding"]) == [
        "50205",
        "50210",
        "51205",
        "51210",
        "53006",
        "53011",
    ]


async def test_diagnostics_when_device_does_not_answer(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test diagnostics still return the last values without a raw dump."""
    await setup_integration(hass, mock_config_entry)
    mock_modbus_unit.fail_requests(ModbusTimeoutError("timed out"))

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert diag["raw"] is None
    assert diag["raw_error"] == "timed out"
    assert diag["values"]["d_serial"] == "**REDACTED**"
