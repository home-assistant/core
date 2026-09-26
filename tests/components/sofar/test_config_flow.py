"""Tests for the Sofar config flow."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, _patch, patch

from modbus_connection import ModbusSerialParams, ModbusTcpParams, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant import config_entries
from homeassistant.components.sofar.config_flow import (
    STEP_RECONFIGURE_SERIAL,
    STEP_RECONFIGURE_TCP,
)
from homeassistant.components.sofar.const import (
    CONF_BAUDRATE,
    CONF_UNIT_ID,
    DEFAULT_NAME,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)
from homeassistant.config_entries import (
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import (
    MOCK_ENTRY_DATA,
    MOCK_MODEL,
    MOCK_SERIAL,
    MOCK_SERIAL_ENTRY_DATA,
    MOCK_SERIAL_INPUT,
    MOCK_TCP_INPUT,
    seed_pv_inverter,
)

from tests.common import MockConfigEntry, get_schema_suggested_value

# A recognized prefix with no model in sofar-modbus's own table.
_UNMODELED_SERIAL = "SA1XXES100XX"


def _patch_temporary_unit(connection: MockModbusConnection) -> _patch:
    """Stand in for async_get_temporary_unit, handing out a unit on connection."""

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant,
        params: ModbusSerialParams | ModbusTcpParams,
        unit_id: int,
    ) -> AsyncIterator[MockModbusUnit]:
        yield connection.for_unit(unit_id)

    return patch(
        "homeassistant.components.sofar.config_flow.async_get_temporary_unit",
        side_effect=_get_temporary_unit,
    )


def _patch_unit(connection: MockModbusConnection) -> _patch:
    """Stand in for async_get_unit, handing out a unit on connection."""
    return patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: connection.for_unit(unit_id),
    )


class _RaisingTemporaryUnit:
    """Stand in for a temporary-unit context whose __aenter__ raises."""

    def __init__(self, error: Exception) -> None:
        """Initialize with the error to raise on entry."""
        self._error = error

    async def __aenter__(self) -> None:
        raise self._error

    async def __aexit__(self, *args: object) -> None:
        """No cleanup: entry never succeeded."""


async def _start_flow(hass: HomeAssistant, connection_type: str) -> str:
    """Open the flow, pick a connection type, and return the flow ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == [TYPE_TCP, TYPE_SERIAL]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": connection_type}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == connection_type
    assert result["errors"] == {}

    return result["flow_id"]


@pytest.mark.parametrize(
    ("connection_type", "user_input", "expected_params", "expected_data"),
    [
        pytest.param(
            TYPE_TCP,
            {**MOCK_TCP_INPUT, CONF_PORT: 1502},
            ModbusTcpParams(host="192.168.1.100", port=1502),
            {**MOCK_ENTRY_DATA, CONF_PORT: 1502},
            id="tcp",
        ),
        pytest.param(
            TYPE_SERIAL,
            {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200},
            ModbusSerialParams(device="/dev/ttyUSB0", baudrate=19200),
            {**MOCK_SERIAL_ENTRY_DATA, CONF_BAUDRATE: 19200},
            id="serial",
        ),
    ],
)
async def test_user_step_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    connection_type: str,
    user_input: dict[str, Any],
    expected_params: ModbusSerialParams | ModbusTcpParams,
    expected_data: dict[str, Any],
) -> None:
    """Test each connection type probes the inverter and creates an entry."""
    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1))
    flow_id = await _start_flow(hass, connection_type)

    with _patch_temporary_unit(mock_conn) as mock_temporary_unit:
        result = await hass.config_entries.flow.async_configure(flow_id, user_input)

    mock_temporary_unit.assert_called_once_with(hass, expected_params, 1)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_MODEL
    assert result["data"] == expected_data
    assert result["result"].unique_id == MOCK_SERIAL
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_success_without_model(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the flow falls back to the default title for an unknown model."""
    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1), serial=_UNMODELED_SERIAL)
    flow_id = await _start_flow(hass, TYPE_TCP)

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == MOCK_ENTRY_DATA
    assert result["result"].unique_id == _UNMODELED_SERIAL


def _seed_unreachable(unit: MockModbusUnit) -> None:
    unit.fail_requests(ModbusTimeoutError("stuck"))


def _seed_unrecognized(unit: MockModbusUnit) -> None:
    """No-op: unseeded registers already decode to an unrecognized serial."""


@pytest.mark.parametrize(
    ("seed", "expected_error", "expected_placeholders"),
    [
        pytest.param(
            _seed_unreachable,
            "cannot_connect",
            {"error": "stuck"},
            id="cannot_connect",
        ),
        pytest.param(
            _seed_unrecognized,
            "unrecognized_inverter",
            {},
            id="unrecognized_inverter",
        ),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    seed: Callable[[MockModbusUnit], None],
    expected_error: str,
    expected_placeholders: dict[str, str],
) -> None:
    """Test the user step reports the right error and recovers, per failure."""
    mock_conn = MockModbusConnection()
    seed(mock_conn.for_unit(1))
    flow_id = await _start_flow(hass, TYPE_TCP)

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == TYPE_TCP
    assert result["errors"] == {"base": expected_error}
    assert result["description_placeholders"] == expected_placeholders
    # The retry starts from what was typed, not from an empty form.
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HOST)
        == MOCK_TCP_INPUT[CONF_HOST]
    )

    working_conn = MockModbusConnection()
    seed_pv_inverter(working_conn.for_unit(1))

    with _patch_temporary_unit(working_conn):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_link_settings_conflict(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a shared-connection link-settings clash surfaces its own message."""
    error = HomeAssistantError(
        "Modbus device ('192.168.1.100', 502) is already in use with different "
        "link settings"
    )
    flow_id = await _start_flow(hass, TYPE_TCP)

    with patch(
        "homeassistant.components.sofar.config_flow.async_get_temporary_unit",
        return_value=_RaisingTemporaryUnit(error),
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"] == {"error": str(error)}


async def test_user_step_already_configured(hass: HomeAssistant) -> None:
    """Test aborting when the inverter is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_ENTRY_DATA)
    entry.add_to_hass(hass)

    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1))
    flow_id = await _start_flow(hass, TYPE_TCP)

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


_NEW_TCP_INPUT = {**MOCK_TCP_INPUT, CONF_HOST: "192.168.1.200"}


async def _start_reconfigure(
    hass: HomeAssistant, entry: MockConfigEntry, step_id: str
) -> ConfigFlowResult:
    """Open the reconfigure flow, pick a connection, and return its form."""
    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"
    assert result["menu_options"] == [STEP_RECONFIGURE_TCP, STEP_RECONFIGURE_SERIAL]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step_id}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id

    return result


async def test_reconfigure_updates_the_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test reconfigure updates the entry and reloads it."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_ENTRY_DATA)
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_TCP)

    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NEW_TCP_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_TYPE: TYPE_TCP, **_NEW_TCP_INPUT}


async def test_reconfigure_offers_the_current_settings(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the link an entry is on comes back prefilled."""
    entry = _serial_entry()
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_SERIAL)

    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_DEVICE)
        == MOCK_SERIAL_INPUT[CONF_DEVICE]
    )

    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1))
    new_input = {**MOCK_SERIAL_INPUT, CONF_DEVICE: "/dev/ttyUSB1"}

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_input
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_TYPE: TYPE_SERIAL, **new_input}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_unmigrated_entry(hass: HomeAssistant) -> None:
    """Test a disabled entry that skipped migration is treated as TCP."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data=MOCK_TCP_INPUT,
        minor_version=1,
        disabled_by=ConfigEntryDisabler.USER,
    )
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_TCP)

    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HOST)
        == MOCK_TCP_INPUT[CONF_HOST]
    )


async def test_reconfigure_rejects_a_different_serial(hass: HomeAssistant) -> None:
    """Test reconfigure aborts if the inverter's serial doesn't match."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_ENTRY_DATA)
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_TCP)

    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1), serial=_UNMODELED_SERIAL)

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NEW_TCP_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data == MOCK_ENTRY_DATA


@pytest.mark.parametrize(
    ("seed", "expected_error", "expected_placeholders"),
    [
        pytest.param(
            _seed_unreachable,
            "cannot_connect",
            {"error": "stuck"},
            id="cannot_connect",
        ),
        pytest.param(
            _seed_unrecognized,
            "unrecognized_inverter",
            {},
            id="unrecognized_inverter",
        ),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    seed: Callable[[MockModbusUnit], None],
    expected_error: str,
    expected_placeholders: dict[str, str],
) -> None:
    """Test the reconfigure step reports the right error and recovers."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_ENTRY_DATA)
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_TCP)

    mock_conn = MockModbusConnection()
    seed(mock_conn.for_unit(1))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NEW_TCP_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_RECONFIGURE_TCP
    assert result["errors"] == {"base": expected_error}
    assert result["description_placeholders"] == expected_placeholders
    assert entry.data == MOCK_ENTRY_DATA
    # The retry starts from what was typed, not from the stored entry.
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HOST)
        == _NEW_TCP_INPUT[CONF_HOST]
    )

    working_conn = MockModbusConnection()
    seed_pv_inverter(working_conn.for_unit(1))

    with _patch_temporary_unit(working_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NEW_TCP_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_TYPE: TYPE_TCP, **_NEW_TCP_INPUT}


def _serial_entry() -> MockConfigEntry:
    """A config entry for an inverter on a serial port."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data=MOCK_SERIAL_ENTRY_DATA,
        title=MOCK_MODEL,
        minor_version=2,
    )


async def test_reconfigure_new_line_settings(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test new line settings take the entry off the bus before probing.

    One connection cannot serve two baud rates at once.
    """
    entry = _serial_entry()
    entry.add_to_hass(hass)
    states: list[ConfigEntryState] = []

    @asynccontextmanager
    async def _probe_watching_the_entry(
        hass: HomeAssistant,
        params: ModbusSerialParams | ModbusTcpParams,
        unit_id: int,
    ) -> AsyncIterator[MockModbusUnit]:
        states.append(entry.state)
        yield mock_connection.for_unit(unit_id)

    with _patch_unit(mock_connection):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_SERIAL)
        with patch(
            "homeassistant.components.sofar.config_flow.async_get_temporary_unit",
            side_effect=_probe_watching_the_entry,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200}
            )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert states == [ConfigEntryState.NOT_LOADED]
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_BAUDRATE] == 19200
    assert entry.state is ConfigEntryState.LOADED


async def test_reconfigure_new_line_settings_cannot_connect(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a failed probe puts the entry back on the bus it was taken off."""
    entry = _serial_entry()
    entry.add_to_hass(hass)

    with _patch_unit(mock_connection):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        mock_connection.for_unit(1).fail_requests(ModbusTimeoutError("stuck"))

        result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_SERIAL)
        with _patch_temporary_unit(mock_connection):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200}
            )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data == MOCK_SERIAL_ENTRY_DATA
    # Setting the entry back up hits the same dead device, so it
    # lands in retry rather than staying unloaded.
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("entry_data", "step_id", "user_input", "expected_data"),
    [
        pytest.param(
            MOCK_ENTRY_DATA,
            STEP_RECONFIGURE_SERIAL,
            MOCK_SERIAL_INPUT,
            MOCK_SERIAL_ENTRY_DATA,
            id="network_to_serial",
        ),
        pytest.param(
            MOCK_SERIAL_ENTRY_DATA,
            STEP_RECONFIGURE_TCP,
            MOCK_TCP_INPUT,
            MOCK_ENTRY_DATA,
            id="serial_to_network",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_moves_between_connections(
    hass: HomeAssistant,
    entry_data: dict[str, Any],
    step_id: str,
    user_input: dict[str, Any],
    expected_data: dict[str, Any],
) -> None:
    """Test an entry moves to the other connection, keeping its identity."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=MOCK_SERIAL, data=entry_data, minor_version=2
    )
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry, step_id)

    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # Exact equality: the keys of the link it left are gone, not stale.
    assert entry.data == expected_data
    assert entry.unique_id == MOCK_SERIAL


async def test_reconfigure_other_connection_starts_empty(hass: HomeAssistant) -> None:
    """Test the other connection's form is not filled from the current one."""
    entry = _serial_entry()
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry, STEP_RECONFIGURE_TCP)

    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, CONF_HOST) is None
    # The unit ID is the inverter's, so it survives the move.
    assert (
        get_schema_suggested_value(schema, CONF_UNIT_ID)
        == MOCK_SERIAL_INPUT[CONF_UNIT_ID]
    )
