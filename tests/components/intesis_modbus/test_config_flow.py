"""Tests for the Intesis Modbus config flow."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, _patch, patch

from modbus_connection import (
    IllegalDataAddressError,
    ModbusSerialParams,
    ModbusTcpParams,
    ModbusTimeoutError,
    ServerDeviceBusyError,
)
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value

from homeassistant.components.intesis_modbus.const import (
    CONF_BAUDRATE,
    CONF_HAS_VANE,
    CONF_TEMPERATURE_FORMAT,
    CONF_UNIT_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow
from homeassistant.exceptions import HomeAssistantError

from . import (
    MOCK_ENTRY_DATA,
    MOCK_ENTRY_OPTIONS,
    MOCK_TCP_ENTRY_DATA,
    MOCK_TCP_INPUT,
    MOCK_USER_INPUT,
    seed_initialising_single_unit,
    seed_single_unit,
)

TARGET = "homeassistant.components.intesis_modbus.config_flow.async_get_temporary_unit"


def _patch_temporary_unit(
    connection: MockModbusConnection,
    device: str = "/dev/ttyUSB0",
    baudrate: int = 9600,
    on_probe: Callable[[], None] | None = None,
    expected: ModbusSerialParams | ModbusTcpParams | None = None,
) -> _patch:
    """Stand in for async_get_temporary_unit, handing out a unit on connection."""
    if expected is None:
        expected = ModbusSerialParams(
            device=device, baudrate=baudrate, bytesize=8, parity="N", stopbits=2
        )

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant,
        params: ModbusSerialParams | ModbusTcpParams,
        unit_id: int,
    ) -> AsyncIterator[MockModbusUnit]:
        assert params == expected
        if on_probe is not None:
            on_probe()
        yield connection.for_unit(unit_id)

    return patch(TARGET, side_effect=_get_temporary_unit)


class _RaisingTemporaryUnit:
    """Stand in for a temporary-unit context whose __aenter__ raises."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def __aenter__(self) -> None:
        raise self._error

    async def __aexit__(self, *args: object) -> None:
        return None


def _seeded(
    seed: Callable[[MockModbusUnit], None] = seed_single_unit,
) -> MockModbusConnection:
    connection = MockModbusConnection()
    seed(connection.for_unit(1))
    return connection


async def _pick_link(
    hass: HomeAssistant, result: ConfigFlowResult, step_id: str
) -> ConfigFlowResult:
    """Pick a connection type in the menu a flow opens with."""
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step_id}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id
    return result


async def _submit_link(
    hass: HomeAssistant,
    step_id: str = "serial",
    user_input: dict[str, Any] | None = None,
) -> ConfigFlowResult:
    """Start a user flow, pick the connection type and submit its settings.

    Without settings, the serial ones of the mock gateway are submitted.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    result = await _pick_link(hass, result, step_id)
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT if user_input is None else user_input
    )


async def _start_reconfigure(
    hass: HomeAssistant, entry: MockConfigEntry, step_id: str = "reconfigure_serial"
) -> ConfigFlowResult:
    """Start a reconfigure flow and pick the connection type."""
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    return await _pick_link(hass, result, step_id)


async def _finish_features(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    *,
    expected_default: bool = True,
    has_vane: bool = True,
) -> ConfigFlowResult:
    """Confirm the features step, checking what the probe pre-filled."""
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "features"
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HAS_VANE)
        is expected_default
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HAS_VANE: has_vane}
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant) -> None:
    """A gateway that identifies itself only needs the vane confirmed."""
    with _patch_temporary_unit(_seeded()):
        result = await _submit_link(hass)
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "INMBSMHI001R000"
    assert result["data"] == MOCK_ENTRY_DATA
    assert result["options"] == MOCK_ENTRY_OPTIONS


@pytest.mark.usefixtures("mock_setup_entry")
async def test_initialising_gateway_can_be_retried(hass: HomeAssistant) -> None:
    """A gateway that is still starting up is set up once it reports values."""
    connection = _seeded(seed_initialising_single_unit)
    with _patch_temporary_unit(connection):
        result = await _submit_link(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "serial"
        assert result["errors"] == {"base": "gateway_starting"}
        seed_single_unit(connection.for_unit(1))
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_ENTRY_DATA
    assert result["options"] == MOCK_ENTRY_OPTIONS


@pytest.mark.usefixtures("mock_setup_entry")
async def test_vane_at_init_value_defaults_to_no_vane(hass: HomeAssistant) -> None:
    """A unit that never reported a vane position is offered without one."""
    connection = _seeded()
    connection.for_unit(1).holding[3] = 0x8000
    with _patch_temporary_unit(connection):
        result = await _submit_link(hass)
    result = await _finish_features(
        hass, result, expected_default=False, has_vane=False
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_ENTRY_DATA
    assert result["options"] == {CONF_HAS_VANE: False}


@pytest.mark.parametrize(
    ("device_id", "brand"),
    [
        pytest.param(0x0801, "Daikin", id="daikin"),
        pytest.param(0x1500, "Panasonic", id="panasonic"),
        pytest.param(0x1F00, "Toshiba", id="toshiba"),
        pytest.param(0x1000, "LG", id="lg"),
        pytest.param(0x1400, "Hitachi", id="hitachi"),
        pytest.param(0x1200, "Samsung", id="samsung"),
    ],
)
async def test_untabled_brand_aborts(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, device_id: int, brand: str
) -> None:
    """A gateway of a brand without code tables is refused by name."""
    connection = _seeded()
    connection.for_unit(1).holding[49] = device_id
    with _patch_temporary_unit(connection):
        result = await _submit_link(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_brand"
    assert result["description_placeholders"] == {"brand": brand}
    assert mock_setup_entry.call_count == 0


@pytest.mark.usefixtures("mock_setup_entry")
async def test_other_device_on_the_line_can_be_corrected(hass: HomeAssistant) -> None:
    """A unit ID that reaches another device is corrected in the same flow."""
    connection = _seeded()
    connection.for_unit(1).holding[49] = 0x7777
    seed_single_unit(connection.for_unit(2))
    with _patch_temporary_unit(connection):
        result = await _submit_link(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "serial"
        assert result["errors"] == {"base": "unsupported_device"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_USER_INPUT, CONF_UNIT_ID: 2}
        )
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**MOCK_ENTRY_DATA, CONF_UNIT_ID: 2}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_refused_device_id_register_can_be_retried(hass: HomeAssistant) -> None:
    """A device that refuses the device id register is not a gateway."""
    connection = _seeded()
    connection.for_unit(1).fail_read(49, IllegalDataAddressError())
    with _patch_temporary_unit(connection):
        result = await _submit_link(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unsupported_device"}
        connection.for_unit(1).fail_read(49, None)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_ENTRY_DATA


@pytest.mark.usefixtures("mock_setup_entry")
async def test_busy_gateway_can_be_retried(hass: HomeAssistant) -> None:
    """A gateway that answers busy is a connection error, not another device."""
    connection = _seeded()
    connection.for_unit(1).fail_read(49, ServerDeviceBusyError())
    with _patch_temporary_unit(connection):
        result = await _submit_link(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
        connection.for_unit(1).fail_read(49, None)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_ENTRY_DATA
    assert result["options"] == MOCK_ENTRY_OPTIONS


@pytest.mark.usefixtures("mock_setup_entry")
async def test_cannot_connect(hass: HomeAssistant) -> None:
    """A silent gateway shows cannot_connect and the flow can be retried."""
    connection = _seeded()
    connection.for_unit(1).fail_requests(ModbusTimeoutError())
    with _patch_temporary_unit(connection):
        result = await _submit_link(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
        connection.for_unit(1).fail_requests(None)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_ENTRY_DATA
    assert result["options"] == MOCK_ENTRY_OPTIONS


@pytest.mark.usefixtures("mock_setup_entry")
async def test_serial_port_in_use_with_other_settings(hass: HomeAssistant) -> None:
    """A port held by another entry with other link settings cannot be probed."""
    with patch(
        TARGET, return_value=_RaisingTemporaryUnit(HomeAssistantError("in use"))
    ):
        result = await _submit_link(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "device_in_use"}
    with _patch_temporary_unit(_seeded()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_ENTRY_DATA
    assert result["options"] == MOCK_ENTRY_OPTIONS


async def test_duplicate_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The same port and unit id cannot be set up twice."""
    mock_config_entry.add_to_hass(hass)
    with _patch_temporary_unit(_seeded()):
        result = await _submit_link(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_overlapping_flows_create_one_entry(hass: HomeAssistant) -> None:
    """Two flows for the same gateway that both pass the probe end in one entry."""
    with _patch_temporary_unit(_seeded()):
        first = await _submit_link(hass)
        second = await _submit_link(hass)
    first = await _finish_features(hass, first)
    assert first["type"] is FlowResultType.CREATE_ENTRY
    second = await _finish_features(hass, second)
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_second_gateway_on_same_port(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Another unit id on a port that is already set up is a new entry."""
    mock_config_entry.add_to_hass(hass)
    connection = MockModbusConnection()
    seed_single_unit(connection.for_unit(2))
    with _patch_temporary_unit(connection):
        result = await _submit_link(
            hass, user_input={**MOCK_USER_INPUT, CONF_UNIT_ID: 2}
        )
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**MOCK_ENTRY_DATA, CONF_UNIT_ID: 2}
    assert result["options"] == MOCK_ENTRY_OPTIONS


MOVED_INPUT = {**MOCK_USER_INPUT, CONF_DEVICE: "/dev/ttyUSB1"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_moves_the_gateway_to_another_port(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Reconfiguring points the entry at the port the gateway moved to."""
    mock_config_entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, mock_config_entry)
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_DEVICE)
        == "/dev/ttyUSB0"
    )
    with _patch_temporary_unit(_seeded(), "/dev/ttyUSB1"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOVED_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {**MOCK_ENTRY_DATA, CONF_DEVICE: "/dev/ttyUSB1"}
    assert mock_config_entry.options == MOCK_ENTRY_OPTIONS


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_keeps_the_fields_left_out(hass: HomeAssistant) -> None:
    """A submission with only a new port keeps the entry's baud rate and unit ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_ENTRY_DATA, CONF_BAUDRATE: 19200, CONF_UNIT_ID: 2},
        options=MOCK_ENTRY_OPTIONS,
    )
    entry.add_to_hass(hass)
    connection = MockModbusConnection()
    seed_single_unit(connection.for_unit(2))
    result = await _start_reconfigure(hass, entry)
    with _patch_temporary_unit(connection, "/dev/ttyUSB1", baudrate=19200):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "/dev/ttyUSB1"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        **MOCK_ENTRY_DATA,
        CONF_DEVICE: "/dev/ttyUSB1",
        CONF_BAUDRATE: 19200,
        CONF_UNIT_ID: 2,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_can_be_retried(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A gateway that does not answer at first is reconfigured once it does."""
    mock_config_entry.add_to_hass(hass)
    connection = _seeded()
    connection.for_unit(1).fail_requests(ModbusTimeoutError())
    result = await _start_reconfigure(hass, mock_config_entry)
    with _patch_temporary_unit(connection, "/dev/ttyUSB1"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOVED_INPUT
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure_serial"
        assert result["errors"] == {"base": "cannot_connect"}
        connection.for_unit(1).fail_requests(None)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOVED_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_DEVICE] == "/dev/ttyUSB1"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_picks_up_the_temperature_format(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The format the gateway reports now replaces the one saved at setup."""
    mock_config_entry.add_to_hass(hass)
    connection = _seeded()
    for address, value in {4: 22, 5: 20, 23: 22, 24: 30, 25: 16}.items():
        connection.for_unit(1).holding[address] = value
    result = await _start_reconfigure(hass, mock_config_entry)
    with _patch_temporary_unit(connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_TEMPERATURE_FORMAT] == "celsius"


async def test_reconfigure_onto_another_entry_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Two entries cannot end up on the same port and unit id."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_ENTRY_DATA, CONF_DEVICE: "/dev/ttyUSB1"},
        options=MOCK_ENTRY_OPTIONS,
    ).add_to_hass(hass)
    result = await _start_reconfigure(hass, mock_config_entry)
    with _patch_temporary_unit(_seeded(), "/dev/ttyUSB1"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOVED_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == MOCK_ENTRY_DATA


async def test_reconfigure_recheck_finds_an_entry_added_meanwhile(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A gateway another flow claimed during the probe is not taken twice."""
    mock_config_entry.add_to_hass(hass)

    def _claim() -> None:
        MockConfigEntry(
            domain=DOMAIN,
            data={**MOCK_ENTRY_DATA, CONF_DEVICE: "/dev/ttyUSB1"},
            options=MOCK_ENTRY_OPTIONS,
        ).add_to_hass(hass)

    result = await _start_reconfigure(hass, mock_config_entry)
    with _patch_temporary_unit(_seeded(), "/dev/ttyUSB1", on_probe=_claim):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOVED_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == MOCK_ENTRY_DATA


FASTER_INPUT = {**MOCK_USER_INPUT, CONF_BAUDRATE: 19200}


async def test_reconfigure_changes_the_baud_rate_of_a_loaded_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """The entry lets go of the port, which it holds at the old baud rate."""
    states: list[ConfigEntryState] = []
    result = await _start_reconfigure(hass, init_integration)
    with _patch_temporary_unit(
        _seeded(),
        baudrate=19200,
        on_probe=lambda: states.append(init_integration.state),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FASTER_INPUT
        )
    await hass.async_block_till_done()
    assert states == [ConfigEntryState.NOT_LOADED]
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.data == {**MOCK_ENTRY_DATA, CONF_BAUDRATE: 19200}
    assert init_integration.state is ConfigEntryState.LOADED
    assert mock_get_unit.call_args.args[2].baudrate == 19200


async def test_reconfigure_changes_the_baud_rate_of_an_entry_retrying_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """An entry retrying at the wrong baud rate stops retrying during the probe."""
    mock_connection.for_unit(1).fail_requests(ModbusTimeoutError())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    states: list[ConfigEntryState] = []
    mock_connection.for_unit(1).fail_requests(None)
    result = await _start_reconfigure(hass, mock_config_entry)
    with _patch_temporary_unit(
        _seeded(),
        baudrate=19200,
        on_probe=lambda: states.append(mock_config_entry.state),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FASTER_INPUT
        )
    await hass.async_block_till_done()
    assert states == [ConfigEntryState.NOT_LOADED]
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {**MOCK_ENTRY_DATA, CONF_BAUDRATE: 19200}
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_get_unit.call_args.args[2].baudrate == 19200


async def test_reconfigure_puts_a_loaded_entry_back_when_the_probe_fails(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A gateway that does not answer at the new baud rate keeps the old one."""
    states: list[ConfigEntryState] = []
    connection = _seeded()
    connection.for_unit(1).fail_requests(ModbusTimeoutError())
    result = await _start_reconfigure(hass, init_integration)
    with _patch_temporary_unit(
        connection,
        baudrate=19200,
        on_probe=lambda: states.append(init_integration.state),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FASTER_INPUT
        )
        assert states == [ConfigEntryState.NOT_LOADED]
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
        assert init_integration.data == MOCK_ENTRY_DATA
        assert init_integration.state is ConfigEntryState.LOADED

        connection.for_unit(1).fail_requests(None)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FASTER_INPUT
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.data == {**MOCK_ENTRY_DATA, CONF_BAUDRATE: 19200}
    assert init_integration.state is ConfigEntryState.LOADED


async def test_reconfigure_keeps_a_loaded_entry_running_on_another_port(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Probing another port does not need the entry to let go of its own."""
    states: list[ConfigEntryState] = []
    result = await _start_reconfigure(hass, init_integration)
    with _patch_temporary_unit(
        _seeded(),
        "/dev/ttyUSB1",
        on_probe=lambda: states.append(init_integration.state),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOVED_INPUT
        )
    await hass.async_block_till_done()
    assert states == [ConfigEntryState.LOADED]
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_recovers_from_a_port_in_use(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A port another entry holds with other settings can be tried again."""
    mock_config_entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, mock_config_entry)
    with patch(
        TARGET, return_value=_RaisingTemporaryUnit(HomeAssistantError("in use"))
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOVED_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_serial"
    assert result["errors"] == {"base": "device_in_use"}
    with _patch_temporary_unit(_seeded(), "/dev/ttyUSB1"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOVED_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {**MOCK_ENTRY_DATA, CONF_DEVICE: "/dev/ttyUSB1"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_recovers_from_another_device_on_the_line(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A unit ID that reaches another device is corrected in the same flow."""
    mock_config_entry.add_to_hass(hass)
    connection = _seeded()
    connection.for_unit(1).holding[49] = 0x7777
    seed_single_unit(connection.for_unit(2))
    result = await _start_reconfigure(hass, mock_config_entry)
    with _patch_temporary_unit(connection, "/dev/ttyUSB1"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOVED_INPUT
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unsupported_device"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOVED_INPUT, CONF_UNIT_ID: 2}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        **MOCK_ENTRY_DATA,
        CONF_DEVICE: "/dev/ttyUSB1",
        CONF_UNIT_ID: 2,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_recovers_from_a_gateway_that_is_starting(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A gateway that is still starting up is saved once it reports values."""
    mock_config_entry.add_to_hass(hass)
    connection = _seeded(seed_initialising_single_unit)
    result = await _start_reconfigure(hass, mock_config_entry)
    with _patch_temporary_unit(connection, "/dev/ttyUSB1"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOVED_INPUT
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "gateway_starting"}
        seed_single_unit(connection.for_unit(1))
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOVED_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {**MOCK_ENTRY_DATA, CONF_DEVICE: "/dev/ttyUSB1"}


async def test_reconfigure_puts_a_loaded_entry_back_on_an_unsupported_brand(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A gateway of another brand at the new baud rate leaves the entry running."""
    states: list[ConfigEntryState] = []
    connection = _seeded()
    connection.for_unit(1).holding[49] = 0x0801
    result = await _start_reconfigure(hass, init_integration)
    with _patch_temporary_unit(
        connection,
        baudrate=19200,
        on_probe=lambda: states.append(init_integration.state),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FASTER_INPUT
        )
    await hass.async_block_till_done()
    assert states == [ConfigEntryState.NOT_LOADED]
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_brand"
    assert init_integration.data == MOCK_ENTRY_DATA
    assert init_integration.state is ConfigEntryState.LOADED


async def test_reconfigure_puts_a_loaded_entry_back_when_the_gateway_was_claimed(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A gateway another flow claimed during the probe leaves the entry running."""

    def _claim() -> None:
        MockConfigEntry(
            domain=DOMAIN, data=MOCK_ENTRY_DATA, options=MOCK_ENTRY_OPTIONS
        ).add_to_hass(hass)

    result = await _start_reconfigure(hass, init_integration)
    with _patch_temporary_unit(_seeded(), baudrate=19200, on_probe=_claim):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FASTER_INPUT
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert init_integration.data == MOCK_ENTRY_DATA
    assert init_integration.state is ConfigEntryState.LOADED


async def test_reconfigure_finishes_when_the_request_is_cancelled(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A request dropped while the entry unloads does not leave it unloaded."""
    unloading = asyncio.Event()
    proceed = asyncio.Event()

    unload_platforms = hass.config_entries.async_unload_platforms_or_raise

    async def _slow_unload(entry: MockConfigEntry, platforms: list[Platform]) -> None:
        unloading.set()
        await proceed.wait()
        await unload_platforms(entry, platforms)

    connection = _seeded()
    connection.for_unit(1).fail_requests(ModbusTimeoutError())
    result = await _start_reconfigure(hass, init_integration)
    with (
        patch.object(
            hass.config_entries, "async_unload_platforms_or_raise", _slow_unload
        ),
        _patch_temporary_unit(connection, baudrate=19200),
    ):
        request = hass.async_create_task(
            hass.config_entries.flow.async_configure(result["flow_id"], FASTER_INPUT)
        )
        await unloading.wait()
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        proceed.set()
        await hass.async_block_till_done()
    assert init_integration.data == MOCK_ENTRY_DATA
    assert init_integration.state is ConfigEntryState.LOADED


async def test_reconfigure_aborts_when_the_entry_does_not_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """An entry that keeps holding its port cannot be probed at another rate."""
    result = await _start_reconfigure(hass, init_integration)
    with (
        patch.object(hass.config_entries, "async_unload", return_value=False),
        patch(TARGET) as mock_probe,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FASTER_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unload_failed"
    assert mock_probe.call_count == 0
    assert init_integration.data == MOCK_ENTRY_DATA


async def test_reconfigure_saves_nothing_when_the_flow_was_removed(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A flow aborted during the probe does not change the entry afterwards."""
    result = await _start_reconfigure(hass, init_integration)
    flow_id = result["flow_id"]
    with (
        _patch_temporary_unit(
            _seeded(),
            baudrate=19200,
            on_probe=lambda: hass.config_entries.flow.async_abort(flow_id),
        ),
        pytest.raises(UnknownFlow),
    ):
        await hass.config_entries.flow.async_configure(flow_id, FASTER_INPUT)
    await hass.async_block_till_done()
    assert init_integration.data == MOCK_ENTRY_DATA
    assert init_integration.state is ConfigEntryState.LOADED


async def test_reconfigure_saves_nothing_when_cancelled_during_the_probe(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A request dropped during a probe that would succeed changes nothing."""
    probing = asyncio.Event()
    proceed = asyncio.Event()

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant, params: ModbusSerialParams, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        probing.set()
        await proceed.wait()
        yield _seeded().for_unit(unit_id)

    result = await _start_reconfigure(hass, init_integration)
    with patch(TARGET, side_effect=_get_temporary_unit):
        request = hass.async_create_task(
            hass.config_entries.flow.async_configure(result["flow_id"], FASTER_INPUT)
        )
        await probing.wait()
        assert init_integration.state is ConfigEntryState.NOT_LOADED
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        proceed.set()
        await hass.async_block_till_done()
    assert init_integration.data == MOCK_ENTRY_DATA
    assert init_integration.state is ConfigEntryState.LOADED


async def test_reconfigure_survives_a_reload_during_the_probe(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """An entry something else loaded again during the probe is not an error."""
    connection = _seeded()
    connection.for_unit(1).fail_requests(ModbusTimeoutError())

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant, params: ModbusSerialParams, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        await hass.config_entries.async_setup(init_integration.entry_id)
        yield connection.for_unit(unit_id)

    result = await _start_reconfigure(hass, init_integration)
    with patch(TARGET, side_effect=_get_temporary_unit):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FASTER_INPUT
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
        assert init_integration.state is ConfigEntryState.LOADED

    with _patch_temporary_unit(_seeded(), baudrate=19200):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FASTER_INPUT
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.data == {**MOCK_ENTRY_DATA, CONF_BAUDRATE: 19200}


TCP_PARAMS = ModbusTcpParams(host="192.168.1.50", port=502)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow_through_a_tcp_bridge(hass: HomeAssistant) -> None:
    """A gateway behind a Modbus TCP bridge is set up from its host and port."""
    with _patch_temporary_unit(_seeded(), expected=TCP_PARAMS):
        result = await _submit_link(hass, "tcp", MOCK_TCP_INPUT)
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "INMBSMHI001R000"
    assert result["data"] == MOCK_TCP_ENTRY_DATA
    assert result["options"] == MOCK_ENTRY_OPTIONS


@pytest.mark.usefixtures("mock_setup_entry")
async def test_tcp_bridge_that_does_not_answer_can_be_retried(
    hass: HomeAssistant,
) -> None:
    """A silent bridge shows cannot_connect and the flow can be retried."""
    connection = _seeded()
    connection.for_unit(1).fail_requests(ModbusTimeoutError())
    with _patch_temporary_unit(connection, expected=TCP_PARAMS):
        result = await _submit_link(hass, "tcp", MOCK_TCP_INPUT)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "tcp"
        assert result["errors"] == {"base": "cannot_connect"}
        connection.for_unit(1).fail_requests(None)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_TCP_INPUT
        )
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_TCP_ENTRY_DATA


async def test_tcp_duplicate_aborts_whatever_the_case_of_the_host(
    hass: HomeAssistant,
) -> None:
    """The same bridge and unit ID cannot be set up twice, however it is typed."""
    MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_TCP_ENTRY_DATA, CONF_HOST: "bridge.local"},
        options=MOCK_ENTRY_OPTIONS,
        minor_version=2,
    ).add_to_hass(hass)
    result = await _submit_link(
        hass, "tcp", {**MOCK_TCP_INPUT, CONF_HOST: " Bridge.LOCAL "}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_moves_the_gateway_behind_a_tcp_bridge(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A gateway moved from a serial port to a bridge keeps its entry."""
    mock_config_entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, mock_config_entry, "reconfigure_tcp")
    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, CONF_UNIT_ID) == 1
    assert get_schema_suggested_value(schema, CONF_HOST) is None
    with _patch_temporary_unit(_seeded(), expected=TCP_PARAMS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_TCP_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == MOCK_TCP_ENTRY_DATA
    assert mock_config_entry.options == MOCK_ENTRY_OPTIONS


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_of_a_tcp_entry_keeps_the_fields_left_out(
    hass: HomeAssistant,
) -> None:
    """A submission with only a new host keeps the entry's port and unit ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_TCP_ENTRY_DATA, CONF_PORT: 4196, CONF_UNIT_ID: 2},
        options=MOCK_ENTRY_OPTIONS,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    connection = MockModbusConnection()
    seed_single_unit(connection.for_unit(2))
    result = await _start_reconfigure(hass, entry, "reconfigure_tcp")
    with _patch_temporary_unit(
        connection, expected=ModbusTcpParams(host="192.168.1.60", port=4196)
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.60"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        **MOCK_TCP_ENTRY_DATA,
        CONF_HOST: "192.168.1.60",
        CONF_PORT: 4196,
        CONF_UNIT_ID: 2,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_moves_a_tcp_entry_to_a_serial_port(
    hass: HomeAssistant,
) -> None:
    """A gateway moved from a bridge to a serial port drops the bridge settings."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_TCP_ENTRY_DATA,
        options=MOCK_ENTRY_OPTIONS,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry)
    with _patch_temporary_unit(_seeded()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == MOCK_ENTRY_DATA
    assert entry.data[CONF_TYPE] == "serial"
