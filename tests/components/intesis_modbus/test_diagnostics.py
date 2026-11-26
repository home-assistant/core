"""Tests for the Intesis Modbus diagnostics."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import IllegalDataAddressError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.intesis_modbus.const import DOMAIN
from homeassistant.components.intesis_modbus.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from . import MOCK_ENTRY_OPTIONS, MOCK_TCP_ENTRY_DATA


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


async def test_diagnostics_report_the_most_recent_poll(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """A poll in which every block failed replaces the report of the last good one."""
    unit = mock_connection.for_unit(1)
    for address in (0, 13, 21, 31, 46, 55, 60, 65, 81, 97):
        unit.fail_read(address, IllegalDataAddressError())
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    assert result["updated"] == []
    assert sorted(result["failed"]) == [
        "control",
        "diagnostics",
        "limits",
        "lock",
        "status",
        "temperatures",
        "window",
    ]


async def test_diagnostics_after_a_poll_the_gateway_did_not_answer(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """A poll that got no answer at all leaves no report to show."""
    mock_connection.for_unit(1).fail_requests(ModbusTimeoutError())
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    assert result["updated"] is None
    assert result["failed"] is None
    assert result["read_error"] == "ModbusTimeoutError"


async def test_diagnostics_do_not_tell_where_the_bridge_is(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_get_unit: MagicMock,
) -> None:
    """The host of a Modbus TCP bridge is left out of a shared download."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_TCP_ENTRY_DATA,
        options=MOCK_ENTRY_OPTIONS,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert result["entry"][CONF_HOST] == "**REDACTED**"
    assert result["entry"][CONF_PORT] == 502
    assert result["registers"] is not None


async def test_diagnostics_scrub_the_bridge_from_failures(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """A failed block whose error names the bridge does not give its host away."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_TCP_ENTRY_DATA,
        options=MOCK_ENTRY_OPTIONS,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_connection.for_unit(1).fail_read(
        60, IllegalDataAddressError("no answer from 192.168.1.50:502")
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert "192.168.1.50" not in result["failed"]["temperatures"]
    assert "**REDACTED**" in result["failed"]["temperatures"]
