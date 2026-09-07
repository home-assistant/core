"""An LLM API for reading the registers of a device Home Assistant is talking to.

Bringing a Modbus device up means reading raw registers and comparing them
against a vendor datasheet. That normally needs a second connection alongside
Home Assistant's, competing with it for a bus that answers one request at a
time. The connections here are already open and already serialized, so an
assistant can read through them instead.

Read-only on purpose. A write to the wrong register on a heat pump or an
inverter is not a mistake a model should be able to make on a user's behalf.
"""

from typing import Any, Final, cast, override

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.util.json import JsonObjectType

from .connection import (
    DATA_MODBUS_CONNECTIONS,
    async_get_connection_info,
    async_get_temporary_unit,
)

API_ID: Final = "modbus"

# What the protocol allows: a unit is addressed 1-247 (0 is a broadcast, which
# has no reply to read), a register address is 16-bit, and one request may not
# span more than 125 registers.
MIN_UNIT_ID: Final = 1
MAX_UNIT_ID: Final = 247
MAX_ADDRESS: Final = 0xFFFF

# The four tables a device serves, and how many of each one request may carry:
# registers are 16 bits and capped at 125, single-bit tables at 2000. Each is
# its own address space, so address 0 means a different thing in each.
MAX_REGISTER_COUNT: Final = 125
MAX_BIT_COUNT: Final = 2000
TABLE_LIMITS: Final[dict[str, int]] = {
    "holding": MAX_REGISTER_COUNT,
    "input": MAX_REGISTER_COUNT,
    "coil": MAX_BIT_COUNT,
    "discrete_input": MAX_BIT_COUNT,
}


def _fits_the_table(block: dict[str, Any]) -> dict[str, Any]:
    """Reject a block the table cannot answer, rather than sending it."""
    limit = TABLE_LIMITS[block["table"]]
    if block["count"] > limit:
        raise vol.Invalid(
            f"one request may carry {limit} of the {block['table']} table, "
            f"not {block['count']}"
        )
    if block["address"] + block["count"] - 1 > MAX_ADDRESS:
        raise vol.Invalid(
            f"a block of {block['count']} from {block['address']} runs past "
            f"the last address ({MAX_ADDRESS})"
        )
    return block


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register the Modbus LLM API."""
    llm.async_register_api(hass, ModbusAPI(hass=hass, id=API_ID, name="Modbus"))


class ModbusAPI(llm.API):
    """Read the registers of the devices Home Assistant has connections to."""

    @override
    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the tools, over whatever connections are open right now."""
        return llm.APIInstance(
            api=self,
            api_prompt=(
                "Read Modbus registers from the devices Home Assistant is "
                "connected to. Call list_modbus_devices first: it names the "
                "endpoints you may read from, and read_modbus_block only "
                "accepts one of those. Everything is read-only here. A device "
                "answers one request at a time, so read the block you need "
                "rather than one register at a time."
            ),
            llm_context=llm_context,
            tools=[ListModbusDevicesTool(), ReadModbusBlockTool()],
        )


class ListModbusDevicesTool(llm.Tool):
    """Name the devices that can be read."""

    name = "list_modbus_devices"
    description = (
        "List the Modbus devices Home Assistant holds a connection to. "
        "Returns each device's endpoint, which read_modbus_block takes, "
        "and the unit ids in use on it, keyed by the config entry using them."
    )

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Return the open connections."""
        return {
            "devices": [
                {
                    "endpoint": list(info.endpoint),
                    "connected": info.connected,
                    # A mapping of JSON scalars, which the type cannot express
                    # because dict and list are invariant in their contents.
                    "units": cast(JsonObjectType, info.units),
                }
                for info in async_get_connection_info(hass)
            ]
        }


class ReadModbusBlockTool(llm.Tool):
    """Read a block from one of a device's four tables."""

    name = "read_modbus_block"
    description = (
        "Read a block from a Modbus device, to compare against a datasheet. "
        "Give the endpoint from list_modbus_devices, the unit id, which table "
        "to read, the first address and how many to read. The four tables are "
        "separate address spaces: holding and input hold 16-bit registers, "
        "coil and discrete_input hold single bits."
    )
    parameters = vol.Schema(
        vol.All(
            {
                vol.Required("endpoint"): [vol.Any(str, int)],
                vol.Required("unit_id"): vol.All(
                    int, vol.Range(min=MIN_UNIT_ID, max=MAX_UNIT_ID)
                ),
                vol.Required("address"): vol.All(
                    int, vol.Range(min=0, max=MAX_ADDRESS)
                ),
                vol.Required("count"): vol.All(
                    int, vol.Range(min=1, max=MAX_BIT_COUNT)
                ),
                vol.Optional("table", default="holding"): vol.In(TABLE_LIMITS),
            },
            _fits_the_table,
        )
    )

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Read the block, over the connection that is already open."""
        # The caller is not required to have validated against `parameters`,
        # and this reaches real hardware, so check the block here as well.
        args: dict[str, Any] = self.parameters(tool_input.tool_args)
        endpoint = tuple(args["endpoint"])

        unit_id: int = args["unit_id"]
        shared = hass.data.get(DATA_MODBUS_CONNECTIONS, {}).get(endpoint)

        # Only a unit some config entry holds may be read. The endpoint alone
        # would let a caller reach any address on a gateway, including devices
        # behind it that no integration asked for, and a connection a config
        # flow is only probing belongs to nothing yet.
        if shared is None or not any(
            unit_id in units for units in shared.units.values()
        ):
            raise HomeAssistantError(
                f"Home Assistant holds no unit {unit_id} on {list(endpoint)}. "
                "Call list_modbus_devices for the units there are."
            )

        address: int = args["address"]
        count: int = args["count"]

        # Held for the read, so unloading the last consumer mid-request cannot
        # close the connection underneath it.
        async with async_get_temporary_unit(hass, shared.params, unit_id) as unit:
            # Spelled out rather than dispatched through a mapping: the
            # register tables answer with ints and the bit tables with bools,
            # which no one callable type covers.
            values: list[int] | list[bool]
            match args["table"]:
                case "input":
                    values = await unit.read_input_registers(address, count)
                case "coil":
                    values = await unit.read_coils(address, count)
                case "discrete_input":
                    values = await unit.read_discrete_inputs(address, count)
                case _:
                    values = await unit.read_holding_registers(address, count)

        return {
            "address": address,
            "table": args["table"],
            "values": list(values),
        }
