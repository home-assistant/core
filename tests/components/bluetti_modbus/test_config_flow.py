"""Tests for the BLUETTI Modbus config flow."""

from typing import Any
from unittest.mock import patch

from bluetti_modbus_lib import get_device
from modbus_connection import (
    AcknowledgeError,
    ModbusConnectionError,
    ModbusTimeoutError,
)
from modbus_connection.exceptions import IllegalDataAddressError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

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


@pytest.mark.parametrize(
    ("request_error", "teardown_error"),
    [
        pytest.param(ModbusTimeoutError("timed out"), None, id="timeout"),
        pytest.param(TimeoutError("timed out"), None, id="bare_timeout"),
        pytest.param(AcknowledgeError(), None, id="still_busy"),
        pytest.param(
            ModbusTimeoutError("timed out"),
            ModbusConnectionError("teardown failed"),
            id="teardown_fails",
        ),
    ],
)
async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    request_error: Exception,
    teardown_error: Exception | None,
) -> None:
    """A device that can't be read surfaces cannot_connect, then the flow recovers."""
    mock_modbus_unit.fail_requests(request_error)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    with patch.object(mock_modbus_unit, "disconnect", side_effect=teardown_error):
        result = await hass.config_entries.flow.async_configure(flow_id, _user_input())

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_modbus_unit.fail_requests(None)
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

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unsupported_device(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A device reporting another model is rejected, then the flow recovers."""
    field = get_device("balco260").get_field("d_inverter_type")
    assert field is not None
    balco260_words = field.encode("Balco260")
    for offset, word in enumerate(field.encode("EP2000")):
        mock_modbus_unit.holding[field.address + offset] = word

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_device"}

    for offset, word in enumerate(balco260_words):
        mock_modbus_unit.holding[field.address + offset] = word
    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    await hass.async_block_till_done()

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
    """A link already claimed with different settings recovers once it's free."""
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


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Setting up the same host, port and unit id twice aborts, before any probe."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id="another-device"
    )
    # Offline: a probe would fail with cannot_connect, so it must not happen.
    mock_modbus_unit.fail_requests(ModbusTimeoutError("offline"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_probes_only_the_fields_setup_reads(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A register setup leaves out of its read plan is not read by the probe either."""
    fault = get_device("balco260").get_field("d_inverter_fault")
    assert fault is not None
    mock_modbus_unit.fail_read(fault.address, IllegalDataAddressError())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_rejects_the_same_serial_at_a_different_endpoint(
    hass: HomeAssistant,
    mock_modbus_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The same device answering at a different address/unit id still aborts."""
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
