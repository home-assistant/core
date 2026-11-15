"""Service calls related dependencies for LCN component."""

from enum import StrEnum, auto
from typing import override

import probatio
import pypck
from pypck.device import DeviceConnection

from homeassistant.const import CommonServiceArgument
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_get_device_and_config_entry

from .const import (
    DOMAIN,
    LED_PORTS,
    LED_STATUS,
    OUTPUT_PORTS,
    RELVARREF,
    SENDKEYCOMMANDS,
    SETPOINTS,
    THRESHOLDS,
    TIME_UNITS,
    VAR_UNITS,
    VARIABLES,
)
from .helpers import LcnConfigEntry, is_states_string


class LcnService(StrEnum):
    """LCN service names."""

    OUTPUT_ABS = auto()
    OUTPUT_REL = auto()
    OUTPUT_TOGGLE = auto()
    RELAYS = auto()
    VAR_ABS = auto()
    VAR_RESET = auto()
    VAR_REL = auto()
    LOCK_REGULATOR = auto()
    LED = auto()
    SEND_KEYS = auto()
    LOCK_KEYS = auto()
    DYN_TEXT = auto()
    PCK = auto()


class LcnServiceArgument(StrEnum):
    """LCN service arguments."""

    BRIGHTNESS = auto()
    KEYS = auto()
    LED = auto()
    OUTPUT = auto()
    PCK = auto()
    ROW = auto()
    SETPOINT = auto()
    STATE = auto()
    TABLE = auto()
    TEXT = auto()
    TIME = auto()
    TIME_UNIT = auto()
    TRANSITION = auto()
    UNIT_OF_MEASUREMENT = auto()
    VALUE = auto()
    VALUE_REFERENCE = auto()
    VARIABLE = auto()


class LcnServiceCall:
    """Parent class for all LCN service calls."""

    schema = probatio.Schema(
        {
            probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
        }
    )
    supports_response = SupportsResponse.NONE

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize service call."""
        self.hass = hass

    def get_device_connection(self, service: ServiceCall) -> DeviceConnection:
        """Get address connection object."""
        entry: LcnConfigEntry
        # device_connections is keyed by the ids of the main devices LCN registers
        # for its modules and groups, so a child device has no connection
        device, entry = async_get_device_and_config_entry(
            self.hass,
            DOMAIN,
            service.data[CommonServiceArgument.DEVICE_ID],
            include_child_devices=False,
        )
        return entry.runtime_data.device_connections[device.id]

    async def async_call_service(self, service: ServiceCall) -> ServiceResponse:
        """Execute service call."""
        raise NotImplementedError


class OutputAbs(LcnServiceCall):
    """Set absolute brightness of output port in percent."""

    schema = LcnServiceCall.schema.extend(
        {
            probatio.Required(LcnServiceArgument.OUTPUT): probatio.All(
                probatio.Upper, probatio.In(OUTPUT_PORTS)
            ),
            probatio.Required(LcnServiceArgument.BRIGHTNESS): probatio.All(
                probatio.Coerce(int), probatio.Percentage()
            ),
            probatio.Optional(LcnServiceArgument.TRANSITION, default=0): probatio.All(
                probatio.Coerce(float), probatio.Range(min=0.0, max=486.0)
            ),
        }
    )

    @override
    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        output = pypck.lcn_defs.OutputPort[service.data[LcnServiceArgument.OUTPUT]]
        brightness = service.data[LcnServiceArgument.BRIGHTNESS]
        transition = pypck.lcn_defs.time_to_ramp_value(
            service.data[LcnServiceArgument.TRANSITION] * 1000
        )

        device_connection = self.get_device_connection(service)
        await device_connection.dim_output(output.value, brightness, transition)


class OutputRel(LcnServiceCall):
    """Set relative brightness of output port in percent."""

    schema = LcnServiceCall.schema.extend(
        {
            probatio.Required(LcnServiceArgument.OUTPUT): probatio.All(
                probatio.Upper, probatio.In(OUTPUT_PORTS)
            ),
            probatio.Required(LcnServiceArgument.BRIGHTNESS): probatio.All(
                probatio.Coerce(int), probatio.Range(min=-100, max=100)
            ),
        }
    )

    @override
    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        output = pypck.lcn_defs.OutputPort[service.data[LcnServiceArgument.OUTPUT]]
        brightness = service.data[LcnServiceArgument.BRIGHTNESS]

        device_connection = self.get_device_connection(service)
        await device_connection.rel_output(output.value, brightness)


class OutputToggle(LcnServiceCall):
    """Toggle output port."""

    schema = LcnServiceCall.schema.extend(
        {
            probatio.Required(LcnServiceArgument.OUTPUT): probatio.All(
                probatio.Upper, probatio.In(OUTPUT_PORTS)
            ),
            probatio.Optional(LcnServiceArgument.TRANSITION, default=0): probatio.All(
                probatio.Coerce(float), probatio.Range(min=0.0, max=486.0)
            ),
        }
    )

    @override
    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        output = pypck.lcn_defs.OutputPort[service.data[LcnServiceArgument.OUTPUT]]
        transition = pypck.lcn_defs.time_to_ramp_value(
            service.data[LcnServiceArgument.TRANSITION] * 1000
        )

        device_connection = self.get_device_connection(service)
        await device_connection.toggle_output(output.value, transition)


class Relays(LcnServiceCall):
    """Set the relays status."""

    schema = LcnServiceCall.schema.extend(
        {probatio.Required(LcnServiceArgument.STATE): is_states_string}
    )

    @override
    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        states = [
            pypck.lcn_defs.RelayStateModifier[state]
            for state in service.data[LcnServiceArgument.STATE]
        ]

        device_connection = self.get_device_connection(service)
        await device_connection.control_relays(states)


class Led(LcnServiceCall):
    """Set the led state."""

    schema = LcnServiceCall.schema.extend(
        {
            probatio.Required(LcnServiceArgument.LED): probatio.All(
                probatio.Upper, probatio.In(LED_PORTS)
            ),
            probatio.Required(LcnServiceArgument.STATE): probatio.All(
                probatio.Upper, probatio.In(LED_STATUS)
            ),
        }
    )

    @override
    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        led = pypck.lcn_defs.LedPort[service.data[LcnServiceArgument.LED]]
        led_state = pypck.lcn_defs.LedStatus[service.data[LcnServiceArgument.STATE]]

        device_connection = self.get_device_connection(service)
        await device_connection.control_led(led, led_state)


class VarAbs(LcnServiceCall):
    """Set absolute value of a variable or setpoint.

    Variable has to be set as counter!
    Regulator setpoints can also be set using R1VARSETPOINT, R2VARSETPOINT.
    """

    schema = LcnServiceCall.schema.extend(
        {
            probatio.Required(LcnServiceArgument.VARIABLE): probatio.All(
                probatio.Upper, probatio.In(VARIABLES + SETPOINTS)
            ),
            probatio.Optional(LcnServiceArgument.VALUE, default=0): probatio.Coerce(
                float
            ),
            probatio.Optional(
                LcnServiceArgument.UNIT_OF_MEASUREMENT, default="native"
            ): probatio.All(probatio.Upper, probatio.In(VAR_UNITS)),
        }
    )

    @override
    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        var = pypck.lcn_defs.Var[service.data[LcnServiceArgument.VARIABLE]]
        value = service.data[LcnServiceArgument.VALUE]
        unit = pypck.lcn_defs.VarUnit.parse(
            service.data[LcnServiceArgument.UNIT_OF_MEASUREMENT]
        )

        device_connection = self.get_device_connection(service)
        await device_connection.var_abs(var, value, unit)


class VarReset(LcnServiceCall):
    """Reset value of variable or setpoint."""

    schema = LcnServiceCall.schema.extend(
        {
            probatio.Required(LcnServiceArgument.VARIABLE): probatio.All(
                probatio.Upper, probatio.In(VARIABLES + SETPOINTS)
            )
        }
    )

    @override
    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        var = pypck.lcn_defs.Var[service.data[LcnServiceArgument.VARIABLE]]

        device_connection = self.get_device_connection(service)
        await device_connection.var_reset(var)


class VarRel(LcnServiceCall):
    """Shift value of a variable, setpoint or threshold."""

    schema = LcnServiceCall.schema.extend(
        {
            probatio.Required(LcnServiceArgument.VARIABLE): probatio.All(
                probatio.Upper, probatio.In(VARIABLES + SETPOINTS + THRESHOLDS)
            ),
            probatio.Optional(LcnServiceArgument.VALUE, default=0): probatio.Coerce(
                float
            ),
            probatio.Optional(
                LcnServiceArgument.UNIT_OF_MEASUREMENT, default="native"
            ): probatio.All(probatio.Upper, probatio.In(VAR_UNITS)),
            probatio.Optional(
                LcnServiceArgument.VALUE_REFERENCE, default="current"
            ): probatio.All(probatio.Upper, probatio.In(RELVARREF)),
        }
    )

    @override
    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        var = pypck.lcn_defs.Var[service.data[LcnServiceArgument.VARIABLE]]
        value = service.data[LcnServiceArgument.VALUE]
        unit = pypck.lcn_defs.VarUnit.parse(
            service.data[LcnServiceArgument.UNIT_OF_MEASUREMENT]
        )
        value_ref = pypck.lcn_defs.RelVarRef[
            service.data[LcnServiceArgument.VALUE_REFERENCE]
        ]

        device_connection = self.get_device_connection(service)
        await device_connection.var_rel(var, value, unit, value_ref)


class LockRegulator(LcnServiceCall):
    """Locks a regulator setpoint."""

    schema = LcnServiceCall.schema.extend(
        {
            probatio.Required(LcnServiceArgument.SETPOINT): probatio.All(
                probatio.Upper, probatio.In(SETPOINTS)
            ),
            probatio.Optional(LcnServiceArgument.STATE, default=False): bool,
        }
    )

    @override
    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        setpoint = pypck.lcn_defs.Var[service.data[LcnServiceArgument.SETPOINT]]
        state = service.data[LcnServiceArgument.STATE]

        reg_id = pypck.lcn_defs.Var.to_set_point_id(setpoint)
        device_connection = self.get_device_connection(service)
        await device_connection.lock_regulator(reg_id, state)


class SendKeys(LcnServiceCall):
    """Sends keys (which executes bound commands)."""

    schema = LcnServiceCall.schema.extend(
        {
            probatio.Required(LcnServiceArgument.KEYS): probatio.All(
                probatio.Upper, cv.matches_regex(r"^([A-D][1-8])+$")
            ),
            probatio.Optional(LcnServiceArgument.STATE, default="hit"): probatio.All(
                probatio.Upper, probatio.In(SENDKEYCOMMANDS)
            ),
            probatio.Optional(LcnServiceArgument.TIME, default=0): cv.positive_int,
            probatio.Optional(LcnServiceArgument.TIME_UNIT, default="S"): probatio.All(
                probatio.Upper, probatio.In(TIME_UNITS)
            ),
        }
    )

    @override
    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        device_connection = self.get_device_connection(service)

        keys = [[False] * 8 for i in range(4)]

        key_strings = zip(
            service.data[LcnServiceArgument.KEYS][::2],
            service.data[LcnServiceArgument.KEYS][1::2],
            strict=False,
        )

        for table, key in key_strings:
            table_id = ord(table) - 65
            key_id = int(key) - 1
            keys[table_id][key_id] = True

        if (delay_time := service.data[LcnServiceArgument.TIME]) != 0:
            hit = pypck.lcn_defs.SendKeyCommand.HIT
            if (
                pypck.lcn_defs.SendKeyCommand[service.data[LcnServiceArgument.STATE]]
                is not hit
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_send_keys_action",
                )
            delay_unit = pypck.lcn_defs.TimeUnit.parse(
                service.data[LcnServiceArgument.TIME_UNIT]
            )
            await device_connection.send_keys_hit_deferred(keys, delay_time, delay_unit)
        else:
            state = pypck.lcn_defs.SendKeyCommand[
                service.data[LcnServiceArgument.STATE]
            ]
            await device_connection.send_keys(keys, state)


class LockKeys(LcnServiceCall):
    """Lock keys."""

    schema = LcnServiceCall.schema.extend(
        {
            probatio.Optional(LcnServiceArgument.TABLE, default="a"): probatio.All(
                probatio.Upper, cv.matches_regex(r"^[A-D]$")
            ),
            probatio.Required(LcnServiceArgument.STATE): is_states_string,
            probatio.Optional(LcnServiceArgument.TIME, default=0): cv.positive_int,
            probatio.Optional(LcnServiceArgument.TIME_UNIT, default="S"): probatio.All(
                probatio.Upper, probatio.In(TIME_UNITS)
            ),
        }
    )

    @override
    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        device_connection = self.get_device_connection(service)

        states = [
            pypck.lcn_defs.KeyLockStateModifier[state]
            for state in service.data[LcnServiceArgument.STATE]
        ]
        table_id = ord(service.data[LcnServiceArgument.TABLE]) - 65

        if (delay_time := service.data[LcnServiceArgument.TIME]) != 0:
            if table_id != 0:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_lock_keys_table",
                )
            delay_unit = pypck.lcn_defs.TimeUnit.parse(
                service.data[LcnServiceArgument.TIME_UNIT]
            )
            await device_connection.lock_keys_tab_a_temporary(
                delay_time, delay_unit, states
            )
        else:
            await device_connection.lock_keys(table_id, states)


class DynText(LcnServiceCall):
    """Send dynamic text to LCN-GTxD displays."""

    schema = LcnServiceCall.schema.extend(
        {
            probatio.Required(LcnServiceArgument.ROW): probatio.All(
                int, probatio.Range(min=1, max=4)
            ),
            probatio.Required(LcnServiceArgument.TEXT): probatio.All(
                str, probatio.Length(max=60)
            ),
        }
    )

    @override
    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        row_id = service.data[LcnServiceArgument.ROW] - 1
        text = service.data[LcnServiceArgument.TEXT]

        device_connection = self.get_device_connection(service)
        await device_connection.dyn_text(row_id, text)


class Pck(LcnServiceCall):
    """Send arbitrary PCK command."""

    schema = LcnServiceCall.schema.extend(
        {probatio.Required(LcnServiceArgument.PCK): str}
    )

    @override
    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        pck = service.data[LcnServiceArgument.PCK]
        device_connection = self.get_device_connection(service)
        await device_connection.pck(pck)


SERVICES = (
    (LcnService.OUTPUT_ABS, OutputAbs),
    (LcnService.OUTPUT_REL, OutputRel),
    (LcnService.OUTPUT_TOGGLE, OutputToggle),
    (LcnService.RELAYS, Relays),
    (LcnService.VAR_ABS, VarAbs),
    (LcnService.VAR_RESET, VarReset),
    (LcnService.VAR_REL, VarRel),
    (LcnService.LOCK_REGULATOR, LockRegulator),
    (LcnService.LED, Led),
    (LcnService.SEND_KEYS, SendKeys),
    (LcnService.LOCK_KEYS, LockKeys),
    (LcnService.DYN_TEXT, DynText),
    (LcnService.PCK, Pck),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for LCN."""
    for service_name, service in SERVICES:
        hass.services.async_register(
            DOMAIN, service_name, service(hass).async_call_service, service.schema
        )
