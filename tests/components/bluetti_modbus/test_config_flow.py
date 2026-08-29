"""Tests for the BLUETTI Modbus config flow."""

from typing import Any
from unittest.mock import patch

from modbus_connection import AcknowledgeError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit

from homeassistant.components.bluetti_modbus.const import (
    CONF_DEVICE_TYPE,
    CONF_UNIT_ID,
    DEVICE_TYPE_EP2000,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from .conftest import DEVICE_TYPE, HOST, PORT, SERIAL, UNIT_ID, bluetti_data, seed_unit

from tests.common import MockConfigEntry

TITLE = "Balco260"


def _user_input(
    unit_id: int = UNIT_ID, device_type: str = DEVICE_TYPE
) -> dict[str, Any]:
    """Form input for the user step."""
    return {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_UNIT_ID: unit_id,
        CONF_DEVICE_TYPE: device_type,
    }


async def test_user_flow(hass: HomeAssistant) -> None:
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


async def test_user_flow_falls_back_to_link_identity_without_a_serial(
    hass: HomeAssistant, mock_modbus_connection: MockModbusConnection
) -> None:
    """A device type with no serial number field is identified by its link."""
    seed_unit(mock_modbus_connection.for_unit(UNIT_ID), device_type=DEVICE_TYPE_EP2000)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(device_type=DEVICE_TYPE_EP2000)
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None


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


async def test_user_flow_link_settings_in_use(hass: HomeAssistant) -> None:
    """A link already claimed with different settings is not a transient failure."""
    with patch(
        "homeassistant.components.bluetti_modbus.config_flow.async_get_temporary_unit",
        return_value=_ConflictingUnit(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "link_settings_in_use"}


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


async def test_user_flow_unsupported_device_type(hass: HomeAssistant) -> None:
    """A device type the installed library no longer supports is rejected."""
    with patch(
        "homeassistant.components.bluetti_modbus.config_flow.get_device",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_device_type"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Setting up the same host, port and unit id twice aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The device can be reconfigured to a new port."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(unit_id=2)
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_UNIT_ID] == 2


async def test_reconfigure_flow_wrong_device_rejected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """An address that answers as a different device is rejected."""
    mock_config_entry.add_to_hass(hass)
    other_unit = mock_modbus_connection.for_unit(2)
    seed_unit(other_unit)
    other_unit.holding[50206] = 1  # a different serial number

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(unit_id=2)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert mock_config_entry.data[CONF_UNIT_ID] == UNIT_ID


async def test_reconfigure_flow_onto_another_entrys_endpoint_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Reconfiguring onto an endpoint another entry already uses aborts."""
    mock_config_entry.add_to_hass(hass)
    other_entry = MockConfigEntry(
        domain=DOMAIN, title="Other", data=bluetti_data(unit_id=2)
    )
    other_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(unit_id=2)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A reconfigure attempt surfaces cannot_connect, then recovers."""
    mock_config_entry.add_to_hass(hass)
    mock_modbus_unit.fail_requests(ModbusTimeoutError("timed out"))

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_modbus_unit.fail_requests(None)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
