"""Tests for the SolarEdge Modbus config flow."""

from ipaddress import ip_address
from typing import Any

from modbus_connection import ModbusTimeoutError, ServerDeviceFailureError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.solaredge_modbus.config_flow import SECTION_MORE_OPTIONS
from homeassistant.components.solaredge_modbus.const import (
    CONF_UNIT_ID,
    DEFAULT_UNIT_ID,
    DOMAIN,
    TYPE_TCP,
)
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import HOST, PORT, SERIAL_NUMBER, UNIT_ID, async_seed_unit, tcp_data

from tests.common import MockConfigEntry

TITLE = "SolarEdge SE10000H"

# An inverter announcing itself, as captured from a real one.
DISCOVERY_HOST = "10.148.42.116"
DISCOVERY_NAME = "solaredgeinv-7E1DBB39"


def _discovery(
    host: str = DISCOVERY_HOST,
    properties: dict[str, Any] | None = None,
) -> ZeroconfServiceInfo:
    """An mDNS announcement from a SolarEdge inverter."""
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        port=PORT,
        hostname=f"{DISCOVERY_NAME}.local.",
        type="_solaredge-modbus._tcp.local.",
        name=f"{DISCOVERY_NAME}._solaredge-modbus._tcp.local.",
        properties={"MODBUS_ID": "1"} if properties is None else properties,
    )


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


async def test_zeroconf_discovery(hass: HomeAssistant) -> None:
    """An announced inverter is probed, confirmed and set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {
        "name": TITLE,
        "host": DISCOVERY_HOST,
    }

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        CONF_TYPE: TYPE_TCP,
        CONF_HOST: DISCOVERY_HOST,
        CONF_PORT: PORT,
        CONF_UNIT_ID: UNIT_ID,
    }
    assert result["result"].unique_id == SERIAL_NUMBER


async def test_zeroconf_uses_the_announced_device_id(
    hass: HomeAssistant, mock_modbus_connection: MockModbusConnection
) -> None:
    """The announcement's MODBUS_ID says which device to talk to."""
    await async_seed_unit(hass, mock_modbus_connection.for_unit(2))

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery(properties={"MODBUS_ID": "2"}),
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_UNIT_ID] == 2


@pytest.mark.parametrize(
    "properties",
    [
        pytest.param({}, id="absent"),
        pytest.param({"MODBUS_ID": "0"}, id="out of range"),
        pytest.param({"MODBUS_ID": "solaredge"}, id="not a number"),
    ],
)
async def test_zeroconf_falls_back_to_the_default_device_id(
    hass: HomeAssistant, properties: dict[str, Any]
) -> None:
    """An announcement without a usable device ID gets the factory default."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery(properties=properties),
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_UNIT_ID] == DEFAULT_UNIT_ID


async def test_zeroconf_known_inverter_that_moved_is_followed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An inverter announcing itself from a new address updates the entry.

    The device ID is left alone: the entry may be reaching the inverter on one
    the announcement does not mention.
    """
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == DISCOVERY_HOST
    assert mock_config_entry.data[CONF_UNIT_ID] == UNIT_ID


async def test_zeroconf_known_inverter_is_not_probed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """An announcement matching an entry is dropped without asking the device.

    Every inverter announces itself on every restart, and a device that is
    already set up has nothing to tell the flow.
    """
    mock_config_entry.add_to_hass(hass)
    mock_modbus_unit.fail_read(40000, ModbusTimeoutError("timed out"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery(host=HOST)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_unresponsive_device(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """An announcement from a device that will not answer is dropped."""
    mock_modbus_unit.fail_read(40000, ModbusTimeoutError("timed out"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
