"""Test the NeoPool config flow."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from neopool_modbus.exceptions import NeoPoolModbusError, NeoPoolTimeoutError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.neopool.config_flow import SECTION_MORE_OPTIONS
from homeassistant.components.neopool.const import (
    CONF_BAUDRATE,
    CONF_MODBUS_FRAMER,
    CONF_UNIT_ID,
    CONF_USE_LIGHT,
    DEFAULT_BAUDRATE,
    DEFAULT_UNIT_ID,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration
from .conftest import MOCK_HOST, MOCK_PORT, MOCK_SERIAL

pytestmark = pytest.mark.usefixtures("mock_socket_connection")

USER_INPUT = {
    CONF_HOST: MOCK_HOST,
    CONF_PORT: MOCK_PORT,
    CONF_MODBUS_FRAMER: "tcp",
    SECTION_MORE_OPTIONS: {CONF_UNIT_ID: DEFAULT_UNIT_ID},
}
SERIAL_INPUT = {
    CONF_DEVICE: "/dev/ttyUSB0",
    CONF_BAUDRATE: 19200,
    SECTION_MORE_OPTIONS: {CONF_UNIT_ID: DEFAULT_UNIT_ID},
}

_TEMPORARY_UNIT_PATH = (
    "homeassistant.components.neopool.config_flow.async_get_temporary_unit"
)


@asynccontextmanager
async def _different_serial_unit(
    *_args: object, **_kwargs: object
) -> AsyncIterator[MagicMock]:
    """Async context manager that yields a unit reporting a different serial number."""
    unit = MagicMock()
    unit.async_read_holding_registers = AsyncMock(
        return_value=MagicMock(registers=[9999999999])
    )
    yield unit


def _raising_temporary_unit(exc: Exception) -> MagicMock:
    """Return a patch target that raises exc when used as an async context manager."""

    @asynccontextmanager
    async def _raise(*_args: object, **_kwargs: object) -> AsyncIterator[None]:
        raise exc
        yield  # pragma: no cover

    return patch(_TEMPORARY_UNIT_PATH, side_effect=_raise)


async def _advance_to_step(hass: HomeAssistant, step: str) -> dict:
    """Start a user flow and pick a connection type from the menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


@pytest.mark.usefixtures("mock_neopool_client")
async def test_user_flow_tcp(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """A happy-path TCP flow creates the entry."""
    result = await _advance_to_step(hass, TYPE_TCP)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == TYPE_TCP

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"][CONF_TYPE] == TYPE_TCP
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["data"][CONF_PORT] == MOCK_PORT
    assert result["data"][CONF_UNIT_ID] == DEFAULT_UNIT_ID
    assert result["result"].unique_id == MOCK_SERIAL
    assert mock_setup_entry.call_count == 1


@pytest.mark.usefixtures("mock_neopool_client")
async def test_user_flow_serial(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """A happy-path serial flow creates an entry with no host."""
    result = await _advance_to_step(hass, TYPE_SERIAL)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == TYPE_SERIAL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SERIAL_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "/dev/ttyUSB0"
    assert result["data"][CONF_TYPE] == TYPE_SERIAL
    assert result["data"][CONF_DEVICE] == "/dev/ttyUSB0"
    assert result["data"][CONF_BAUDRATE] == 19200
    assert result["data"][CONF_UNIT_ID] == DEFAULT_UNIT_ID
    assert CONF_HOST not in result["data"]
    assert result["result"].unique_id == MOCK_SERIAL
    assert mock_setup_entry.call_count == 1


@pytest.mark.usefixtures("mock_neopool_client")
async def test_user_flow_serial_rejects_non_positive_baudrate(
    hass: HomeAssistant,
) -> None:
    """A non-positive baud rate is rejected by the schema."""
    result = await _advance_to_step(hass, TYPE_SERIAL)

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**SERIAL_INPUT, CONF_BAUDRATE: 0},
        )


@pytest.mark.parametrize("unit_id", [0, 248])
@pytest.mark.usefixtures("mock_neopool_client")
async def test_user_flow_rejects_out_of_range_unit_id(
    hass: HomeAssistant,
    unit_id: int,
) -> None:
    """A unit ID outside the Modbus 1-247 range is rejected by the schema."""
    result = await _advance_to_step(hass, TYPE_TCP)

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**USER_INPUT, SECTION_MORE_OPTIONS: {CONF_UNIT_ID: unit_id}},
        )


@pytest.mark.parametrize(
    ("exc", "expected_error"),
    [
        (NeoPoolTimeoutError("timeout"), "cannot_connect"),
        (NeoPoolModbusError("bad payload"), "cannot_read_modbus"),
    ],
)
@pytest.mark.usefixtures("mock_neopool_client")
async def test_user_flow_probe_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    exc: Exception,
    expected_error: str,
) -> None:
    """Probe-side exceptions map to a form error and the flow recovers."""
    result = await _advance_to_step(hass, TYPE_TCP)

    with _raising_temporary_unit(exc):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_neopool_client")
async def test_user_flow_device_in_use(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """A device held on different link settings surfaces as cannot_connect."""
    result = await _advance_to_step(hass, TYPE_TCP)

    with _raising_temporary_unit(HomeAssistantError("in use")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_neopool_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The flow aborts when the same device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await _advance_to_step(hass, TYPE_TCP)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_neopool_client")
async def test_reconfigure_flow_happy_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A reconfigure flow updates host/port and reloads the entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.0.2.50",
            CONF_PORT: 1502,
            CONF_MODBUS_FRAMER: "tcp",
            SECTION_MORE_OPTIONS: {CONF_UNIT_ID: 2},
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.0.2.50"
    assert mock_config_entry.data[CONF_PORT] == 1502
    assert mock_config_entry.data[CONF_UNIT_ID] == 2

    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_neopool_client")
async def test_reconfigure_flow_serial(
    hass: HomeAssistant,
    mock_config_entry_serial: MockConfigEntry,
) -> None:
    """A serial entry reconfigures through the serial step."""
    mock_config_entry_serial.add_to_hass(hass)

    result = await mock_config_entry_serial.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE: "/dev/ttyUSB1",
            CONF_BAUDRATE: 19200,
            SECTION_MORE_OPTIONS: {CONF_UNIT_ID: DEFAULT_UNIT_ID},
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry_serial.data[CONF_DEVICE] == "/dev/ttyUSB1"
    assert CONF_HOST not in mock_config_entry_serial.data

    await hass.async_block_till_done()
    assert mock_config_entry_serial.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(mock_config_entry_serial.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_neopool_client")
async def test_reconfigure_flow_relink_same_endpoint(
    hass: HomeAssistant,
    mock_config_entry_serial: MockConfigEntry,
) -> None:
    """A new baud rate on the same serial device takes the entry off the bus.

    The device path is unchanged, so the probe shares the endpoint the loaded
    entry holds; the entry has to be unloaded before the new line settings can
    be probed, then the reload brings it back up.
    """
    await setup_integration(hass, mock_config_entry_serial)
    assert mock_config_entry_serial.state is ConfigEntryState.LOADED

    states: list[ConfigEntryState] = []

    @asynccontextmanager
    async def _probe_watching_the_entry(
        *_args: object, **_kwargs: object
    ) -> AsyncIterator[MagicMock]:
        states.append(mock_config_entry_serial.state)
        yield MagicMock()

    result = await mock_config_entry_serial.start_reconfigure_flow(hass)
    with patch(_TEMPORARY_UNIT_PATH, side_effect=_probe_watching_the_entry):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE: "/dev/ttyUSB0",
                CONF_BAUDRATE: 9600,
                SECTION_MORE_OPTIONS: {CONF_UNIT_ID: DEFAULT_UNIT_ID},
            },
        )

    assert states[0] is ConfigEntryState.NOT_LOADED
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry_serial.data[CONF_BAUDRATE] == 9600

    await hass.async_block_till_done()
    assert mock_config_entry_serial.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(mock_config_entry_serial.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_neopool_client")
async def test_reconfigure_flow_relink_aborts_on_failed_unload(
    hass: HomeAssistant,
    mock_config_entry_serial: MockConfigEntry,
) -> None:
    """A failed unload aborts the relink instead of probing a held port.

    The entry still holds the port on its old line settings, so probing the new
    settings could only clash; the flow aborts rather than report a misleading
    error, leaving the entry untouched.
    """
    await setup_integration(hass, mock_config_entry_serial)
    assert mock_config_entry_serial.state is ConfigEntryState.LOADED

    result = await mock_config_entry_serial.start_reconfigure_flow(hass)
    with patch.object(
        hass.config_entries, "async_unload", return_value=False
    ) as mock_unload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE: "/dev/ttyUSB0",
                CONF_BAUDRATE: 9600,
                SECTION_MORE_OPTIONS: {CONF_UNIT_ID: DEFAULT_UNIT_ID},
            },
        )

    assert mock_unload.called
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_unload_failed"
    assert mock_config_entry_serial.data[CONF_BAUDRATE] == DEFAULT_BAUDRATE

    await hass.config_entries.async_unload(mock_config_entry_serial.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_neopool_client")
async def test_reconfigure_flow_relink_restores_on_cancellation(
    hass: HomeAssistant,
    mock_config_entry_serial: MockConfigEntry,
) -> None:
    """A cancelled probe restores the entry it took off the bus.

    Config-flow steps are awaited directly by the HTTP handler; a client
    disconnect cancels the coroutine. The try/finally around the probe must
    put the entry back even when CancelledError is raised mid-probe.
    """
    await setup_integration(hass, mock_config_entry_serial)
    assert mock_config_entry_serial.state is ConfigEntryState.LOADED

    result = await mock_config_entry_serial.start_reconfigure_flow(hass)
    with (
        _raising_temporary_unit(asyncio.CancelledError()),
        pytest.raises(asyncio.CancelledError),
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE: "/dev/ttyUSB0",
                CONF_BAUDRATE: 9600,
                SECTION_MORE_OPTIONS: {CONF_UNIT_ID: DEFAULT_UNIT_ID},
            },
        )

    await hass.async_block_till_done()
    assert mock_config_entry_serial.state is ConfigEntryState.LOADED
    assert mock_config_entry_serial.data[CONF_BAUDRATE] == DEFAULT_BAUDRATE

    await hass.config_entries.async_unload(mock_config_entry_serial.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_neopool_client")
async def test_reconfigure_flow_relink_restores_on_error(
    hass: HomeAssistant,
    mock_config_entry_serial: MockConfigEntry,
) -> None:
    """A failed probe puts the relinked entry back on the bus it was taken off."""
    await setup_integration(hass, mock_config_entry_serial)
    assert mock_config_entry_serial.state is ConfigEntryState.LOADED

    result = await mock_config_entry_serial.start_reconfigure_flow(hass)
    with _raising_temporary_unit(NeoPoolTimeoutError("boom")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE: "/dev/ttyUSB0",
                CONF_BAUDRATE: 9600,
                SECTION_MORE_OPTIONS: {CONF_UNIT_ID: DEFAULT_UNIT_ID},
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_config_entry_serial.data[CONF_BAUDRATE] == DEFAULT_BAUDRATE
    await hass.async_block_till_done()
    assert mock_config_entry_serial.state is ConfigEntryState.LOADED

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE: "/dev/ttyUSB0",
            CONF_BAUDRATE: 9600,
            SECTION_MORE_OPTIONS: {CONF_UNIT_ID: DEFAULT_UNIT_ID},
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry_serial.data[CONF_BAUDRATE] == 9600

    await hass.async_block_till_done()
    assert mock_config_entry_serial.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(mock_config_entry_serial.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_neopool_client")
async def test_reconfigure_flow_relink_restores_on_mismatch(
    hass: HomeAssistant,
    mock_config_entry_serial: MockConfigEntry,
) -> None:
    """A different controller on the new settings restores the relinked entry."""
    await setup_integration(hass, mock_config_entry_serial)
    assert mock_config_entry_serial.state is ConfigEntryState.LOADED

    result = await mock_config_entry_serial.start_reconfigure_flow(hass)
    with (
        patch(_TEMPORARY_UNIT_PATH, side_effect=_different_serial_unit),
        patch(
            "homeassistant.components.neopool.config_flow.async_probe_serial_unit",
            AsyncMock(return_value="9999999999"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE: "/dev/ttyUSB0",
                CONF_BAUDRATE: 9600,
                SECTION_MORE_OPTIONS: {CONF_UNIT_ID: DEFAULT_UNIT_ID},
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "serial_mismatch"
    assert mock_config_entry_serial.data[CONF_BAUDRATE] == DEFAULT_BAUDRATE

    await hass.async_block_till_done()
    assert mock_config_entry_serial.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(mock_config_entry_serial.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("exc", "expected_error"),
    [
        (NeoPoolTimeoutError("timeout"), "cannot_connect"),
        (NeoPoolModbusError("bad payload"), "cannot_read_modbus"),
    ],
)
@pytest.mark.usefixtures("mock_neopool_client")
async def test_reconfigure_flow_probe_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exc: Exception,
    expected_error: str,
) -> None:
    """A reconfigure flow surfaces probe-side errors."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    with _raising_temporary_unit(exc):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.0.2.99",
                CONF_PORT: 502,
                CONF_MODBUS_FRAMER: "tcp",
                SECTION_MORE_OPTIONS: {CONF_UNIT_ID: 1},
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.0.2.99",
            CONF_PORT: 502,
            CONF_MODBUS_FRAMER: "tcp",
            SECTION_MORE_OPTIONS: {CONF_UNIT_ID: 1},
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_neopool_client")
async def test_reconfigure_flow_serial_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A reconfigure that targets a different physical controller is rejected."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    with (
        patch(_TEMPORARY_UNIT_PATH, side_effect=_different_serial_unit),
        patch(
            "homeassistant.components.neopool.config_flow.async_probe_serial_unit",
            AsyncMock(return_value="9999999999"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.0.2.50",
                CONF_PORT: 502,
                CONF_MODBUS_FRAMER: "tcp",
                SECTION_MORE_OPTIONS: {CONF_UNIT_ID: 1},
            },
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "serial_mismatch"


@pytest.mark.usefixtures("mock_neopool_client")
async def test_options_flow_show_form(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Opening the options flow shows the init form."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


@pytest.mark.usefixtures("mock_neopool_client")
async def test_options_flow_save_changes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Submitting the form persists the new option on the config entry."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_USE_LIGHT: True},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_USE_LIGHT] is True

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
