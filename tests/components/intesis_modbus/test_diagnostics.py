"""Tests for the Intesis Modbus diagnostics."""

from unittest.mock import MagicMock

from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """The download carries the raw register map and the last report."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    assert result == snapshot
    assert result["registers"]["holding"]["49"] == 0x0F00


async def test_diagnostics_when_the_gateway_stops_answering(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """A gateway that stops answering still yields a download."""
    mock_connection.for_unit(1).fail_requests(ModbusTimeoutError())
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    assert result["registers"] is None
    assert result["read_error"] == "ModbusTimeoutError"
    assert result["updated"] is not None


async def test_diagnostics_of_entry_that_is_not_set_up(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """An entry still waiting for its gateway yields a download, not an error."""
    mock_connection.for_unit(1).fail_requests(ModbusTimeoutError())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert result == {
        "entry": dict(mock_config_entry.data),
        "options": {"has_vane": True},
        "state": "setup_retry",
        "updated": None,
        "failed": None,
        "read_error": None,
        "registers": None,
    }
