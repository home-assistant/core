"""Tests for the SolarEdge Modbus config flow."""

from typing import Any

from modbus_connection import ModbusTimeoutError, ServerDeviceFailureError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit

from homeassistant.components.solaredge_modbus.config_flow import SECTION_MORE_OPTIONS
from homeassistant.components.solaredge_modbus.const import CONF_UNIT_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOST, PORT, SERIAL_NUMBER, UNIT_ID, async_seed_unit, tcp_data

from tests.common import MockConfigEntry

TITLE = "SolarEdge SE10000H"


# The serial number of a second, different inverter: "OTHER123".
OTHER_SERIAL_REGISTERS = [20308, 18501, 21041, 12851]


def _user_input(unit_id: int = UNIT_ID) -> dict[str, Any]:
    """Form input for the user step, with the sectioned device ID."""
    return {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        SECTION_MORE_OPTIONS: {CONF_UNIT_ID: unit_id},
    }


def _model_registers(model: str) -> dict[int, int]:
    """Registers holding a model name in the SunSpec common block."""
    padded = model.ljust(32, "\0").encode()
    return {
        40020 + index: (padded[index * 2] << 8) | padded[index * 2 + 1]
        for index in range(16)
    }


async def test_user_flow_tcp(hass: HomeAssistant) -> None:
    """An inverter on the network is probed and its entry created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE  # read from the device
    assert result["data"] == tcp_data()
    assert result["result"].unique_id == SERIAL_NUMBER  # the inverter serial


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """An unresponsive device surfaces cannot_connect, then the flow recovers."""
    mock_modbus_unit.fail_read(40000, ModbusTimeoutError("timed out"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # The device answers again.
    mock_modbus_unit.fail_read(40000, None)

    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE


async def test_user_flow_partial_answer(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """An inverter that answers in part is not accepted, then the flow recovers.

    Setting up needs the inverter block as much as the identity block: what
    entities the entry gets is decided from it. Accepting the form here would
    hand the user an entry that setup can only retry.
    """
    mock_modbus_unit.fail_read(40069, ServerDeviceFailureError())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # The inverter answers for its measurements again.
    mock_modbus_unit.fail_read(40069, None)

    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE


async def test_user_flow_no_solaredge_device(
    hass: HomeAssistant, mock_modbus_connection: MockModbusConnection
) -> None:
    """A Modbus device without a SunSpec header surfaces no_solaredge_device."""
    # A device that answers reads but is not a SolarEdge inverter.
    unit = mock_modbus_connection.for_unit(2)
    unit.holding.update(dict.fromkeys(range(40000, 40004), 0))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, _user_input(2))

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_solaredge_device"}


async def test_user_flow_no_serial_number(
    hass: HomeAssistant, mock_modbus_connection: MockModbusConnection
) -> None:
    """An inverter without a serial number cannot be identified and is rejected."""
    # A valid inverter image, but with the serial-number registers zeroed out.
    unit = mock_modbus_connection.for_unit(3)
    await async_seed_unit(hass, unit)
    unit.holding.update(dict.fromkeys(range(40052, 40068), 0))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, _user_input(3))

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_serial_number"}


async def test_user_flow_ev_charger(
    hass: HomeAssistant, mock_modbus_connection: MockModbusConnection
) -> None:
    """A SolarEdge EV charger answers as an inverter, but is rejected."""
    unit = mock_modbus_connection.for_unit(4)
    await async_seed_unit(hass, unit)
    unit.holding.update(_model_registers("SE-EV-SA-KIT"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, _user_input(4))

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "ev_charger"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Setting up the same inverter twice aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """The inverter can be reconfigured to a new device ID."""
    mock_config_entry.add_to_hass(hass)

    # The same inverter, now answering on device ID 2.
    await async_seed_unit(hass, mock_modbus_connection.for_unit(2))

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(2)
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_UNIT_ID] == 2


async def test_reconfigure_flow_wrong_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """Reconfiguring onto a different inverter is rejected."""
    mock_config_entry.add_to_hass(hass)

    await async_seed_unit(
        hass,
        mock_modbus_connection.for_unit(2),
        serial_registers=OTHER_SERIAL_REGISTERS,
    )

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(2)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert mock_config_entry.data[CONF_UNIT_ID] == UNIT_ID


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A reconfigure attempt surfaces cannot_connect, then recovers."""
    mock_config_entry.add_to_hass(hass)
    mock_modbus_unit.fail_read(40000, ModbusTimeoutError("timed out"))

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # The device answers again.
    mock_modbus_unit.fail_read(40000, None)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
