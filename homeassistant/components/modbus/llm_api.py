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

from .connection import DATA_MODBUS_CONNECTIONS, async_get_connection_info

API_ID: Final = "modbus"

# What the protocol allows: a unit is addressed 1-247 (0 is a broadcast, which
# has no reply to read), a register address is 16-bit, and one request may not
# span more than 125 registers.
MIN_UNIT_ID: Final = 1
MAX_UNIT_ID: Final = 247
MAX_ADDRESS: Final = 0xFFFF
MAX_REGISTER_COUNT: Final = 125


def _fits_in_the_address_space(block: dict[str, Any]) -> dict[str, Any]:
    """Reject a block running past the last register rather than sending it."""
    if block["address"] + block["count"] - 1 > MAX_ADDRESS:
        raise vol.Invalid(
            f"a block of {block['count']} from {block['address']} runs past "
            f"the last register ({MAX_ADDRESS})"
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
                "endpoints you may read from, and read_modbus_registers only "
                "accepts one of those. Registers are read-only here. A device "
                "answers one request at a time, so read the block you need "
                "rather than one register at a time."
            ),
            llm_context=llm_context,
            tools=[ListModbusDevicesTool(), ReadModbusRegistersTool()],
        )


class ListModbusDevicesTool(llm.Tool):
    """Name the devices that can be read."""

    name = "list_modbus_devices"
    description = (
        "List the Modbus devices Home Assistant holds a connection to. "
        "Returns each device's endpoint, which read_modbus_registers takes, "
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


class ReadModbusRegistersTool(llm.Tool):
    """Read a block of registers from one device."""

    name = "read_modbus_registers"
    description = (
        "Read a block of registers from a Modbus device, to compare against a "
        "datasheet. Give the endpoint from list_modbus_devices, the unit id, "
        "the first address and how many registers to read."
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
                    int, vol.Range(min=1, max=MAX_REGISTER_COUNT)
                ),
                vol.Optional("register_type", default="holding"): vol.In(
                    ["holding", "input"]
                ),
            },
            _fits_in_the_address_space,
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

        shared = hass.data.get(DATA_MODBUS_CONNECTIONS, {}).get(endpoint)
        if shared is None:
            raise HomeAssistantError(
                f"No Modbus connection to {list(endpoint)}. "
                "Call list_modbus_devices for the ones there are."
            )

        unit = shared.connection.for_unit(args["unit_id"])
        read = (
            unit.read_input_registers
            if args["register_type"] == "input"
            else unit.read_holding_registers
        )
        values = await read(args["address"], args["count"])

        return {
            "address": args["address"],
            "register_type": args["register_type"],
            "values": list(values),
        }
