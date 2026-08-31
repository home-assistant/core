"""Tests for the BLUETTI Modbus config flow."""

from typing import Any
from unittest.mock import patch

from modbus_connection import AcknowledgeError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit

from homeassistant.components.bluetti_modbus.const import CONF_UNIT_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from .conftest import HOST, PORT, SERIAL, UNIT_ID, bluetti_data, seed_unit

from tests.common import MockConfigEntry

TITLE = "Balco260"


def _user_input(unit_id: int = UNIT_ID) -> dict[str, Any]:
    """Form input for the user step."""
    return {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_UNIT_ID: unit_id,
    }


async def test_user_flow(hass: HomeAssistant, mock_modbus_unit: MockModbusUnit) -> None:
    """A device on the network is probed and its entry created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == bluetti_data()
    assert result["result"].unique_id == SERIAL


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """An unresponsive device surfaces cannot_connect, then the flow recovers."""
    mock_modbus_unit.fail_requests(ModbusTimeoutError("timed out"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_modbus_unit.fail_requests(None)

    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE


async def test_user_flow_retries_a_transient_busy_response(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A device that asks for a retry once during the probe does not fail it."""
    read_holding_registers = mock_modbus_unit.read_holding_registers
    attempts = 0

    async def busy_once(address: int, count: int) -> list[int]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise AcknowledgeError
        return await read_holding_registers(address, count)

    with patch.object(mock_modbus_unit, "read_holding_registers", busy_once):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )
        await hass.async_block_till_done()

    assert attempts > 1  # the retry really happened
    assert result["type"] is FlowResultType.CREATE_ENTRY


class _ConflictingUnit:
    """An async context manager standing in for a claimed, incompatible link."""

    async def __aenter__(self) -> None:
        raise HomeAssistantError("already in use with different link settings")

    async def __aexit__(self, *exc_info: object) -> None:
        return None


async def test_user_flow_link_settings_in_use(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A link already claimed with different settings is not a transient failure.

    The form recovers once the conflicting entry is gone, the same as any
    other form error - only the patched-out probe during the first attempt
    made it look permanent.
    """
    with patch(
        "homeassistant.components.bluetti_modbus.config_flow.async_get_temporary_unit",
        return_value=_ConflictingUnit(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        flow_id = result["flow_id"]
        result = await hass.config_entries.flow.async_configure(flow_id, _user_input())

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "link_settings_in_use"}

    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_rejects_a_zero_serial(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A responder reporting serial 0 is not a real device identity."""
    mock_modbus_unit.holding[50206] = 0  # d_serial's least-significant word

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_probe_timeout_surfaces_cannot_connect(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A probe that exceeds async_update_with_retry()'s own budget is not a crash.

    That budget expiring raises a bare TimeoutError, not a ModbusError - it
    must still surface as a form error here, not propagate uncaught.
    """
    mock_modbus_unit.fail_requests(TimeoutError("timed out"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Setting up the same host, port and unit id twice aborts."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id="another-device"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_rejects_the_same_serial_at_a_different_endpoint(
    hass: HomeAssistant,
    mock_modbus_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The same device answering at a different address/unit id still aborts.

    Distinct from test_user_flow_already_configured, which deliberately
    mismatches the existing entry's unique_id to isolate the host/port/
    unit_id link-match path (_async_abort_entries_match) - this isolates
    the other one, _abort_if_unique_id_configured(): a genuinely different
    link (a different unit id here), but the same confirmed serial.
    """
    mock_config_entry.add_to_hass(hass)
    seed_unit(mock_modbus_connection.for_unit(2))  # same default SERIAL

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(unit_id=2)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
