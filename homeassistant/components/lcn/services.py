"""Service calls related dependencies for LCN component."""

from enum import StrEnum, auto
from typing import cast

import pypck
import voluptuous as vol

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BRIGHTNESS,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_ID,
    CONF_STATE,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.util.json import JsonObjectType

from .const import (
    CONF_GROUP,
    CONF_KEYS,
    CONF_LED,
    CONF_MODULE,
    CONF_OUTPUT,
    CONF_PCK,
    CONF_RELVARREF,
    CONF_ROW,
    CONF_SEGMENT_ID,
    CONF_SETPOINT,
    CONF_TABLE,
    CONF_TEXT,
    CONF_TIME,
    CONF_TIME_UNIT,
    CONF_TRANSITION,
    CONF_VALUE,
    CONF_VARIABLE,
    DEVICE_CONNECTIONS,
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
from .helpers import (
    AddressType,
    DeviceConnectionType,
    address_to_device_id,
    is_address,
    is_states_string,
)


class LcnServiceCall:
    """Parent class for all LCN service calls."""

    schema = vol.Schema(
        {
            vol.Optional(CONF_DEVICE_ID): cv.string,
            vol.Optional(CONF_ADDRESS): is_address,
        }
    )
    supports_response = SupportsResponse.NONE

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize service call."""
        self.hass = hass

    def get_device_id(self, service: ServiceCall) -> str:
        """Get device_id from service.data."""
        if CONF_DEVICE_ID not in service.data and CONF_ADDRESS not in service.data:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_device_identifier",
            )

        if CONF_DEVICE_ID in service.data:
            return cast(str, service.data[CONF_DEVICE_ID])

        async_create_issue(
            self.hass,
            DOMAIN,
            "deprecated_address_parameter",
            breaks_in_ha_version="2025.5.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_address_parameter",
        )

        address, host_name = service.data[CONF_ADDRESS]
        device_id = address_to_device_id(self.hass, address, host_name)
        if device_id is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_address",
            )
        return device_id

    def get_device_connection(self, service: ServiceCall) -> DeviceConnectionType:
        """Get address connection object."""
        device_id = self.get_device_id(service)
        device_registry = dr.async_get(self.hass)
        if not (device := device_registry.async_get(device_id)):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_device_id",
                translation_placeholders={"device_id": device_id},
            )

        return self.hass.data[DOMAIN][device.primary_config_entry][DEVICE_CONNECTIONS][
            device_id
        ]

    async def async_call_service(self, service: ServiceCall) -> JsonObjectType | None:
        """Execute service call."""
        raise NotImplementedError


class OutputAbs(LcnServiceCall):
    """Set absolute brightness of output port in percent."""

    schema = LcnServiceCall.schema.extend(
        {
            vol.Required(CONF_OUTPUT): vol.All(vol.Upper, vol.In(OUTPUT_PORTS)),
            vol.Required(CONF_BRIGHTNESS): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional(CONF_TRANSITION, default=0): vol.All(
                vol.Coerce(float), vol.Range(min=0.0, max=486.0)
            ),
        }
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        output = pypck.lcn_defs.OutputPort[service.data[CONF_OUTPUT]]
        brightness = service.data[CONF_BRIGHTNESS]
        transition = pypck.lcn_defs.time_to_ramp_value(
            service.data[CONF_TRANSITION] * 1000
        )

        device_connection = self.get_device_connection(service)
        await device_connection.dim_output(output.value, brightness, transition)


class OutputRel(LcnServiceCall):
    """Set relative brightness of output port in percent."""

    schema = LcnServiceCall.schema.extend(
        {
            vol.Required(CONF_OUTPUT): vol.All(vol.Upper, vol.In(OUTPUT_PORTS)),
            vol.Required(CONF_BRIGHTNESS): vol.All(
                vol.Coerce(int), vol.Range(min=-100, max=100)
            ),
        }
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        output = pypck.lcn_defs.OutputPort[service.data[CONF_OUTPUT]]
        brightness = service.data[CONF_BRIGHTNESS]

        device_connection = self.get_device_connection(service)
        await device_connection.rel_output(output.value, brightness)


class OutputToggle(LcnServiceCall):
    """Toggle output port."""

    schema = LcnServiceCall.schema.extend(
        {
            vol.Required(CONF_OUTPUT): vol.All(vol.Upper, vol.In(OUTPUT_PORTS)),
            vol.Optional(CONF_TRANSITION, default=0): vol.All(
                vol.Coerce(float), vol.Range(min=0.0, max=486.0)
            ),
        }
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        output = pypck.lcn_defs.OutputPort[service.data[CONF_OUTPUT]]
        transition = pypck.lcn_defs.time_to_ramp_value(
            service.data[CONF_TRANSITION] * 1000
        )

        device_connection = self.get_device_connection(service)
        await device_connection.toggle_output(output.value, transition)


class Relays(LcnServiceCall):
    """Set the relays status."""

    schema = LcnServiceCall.schema.extend({vol.Required(CONF_STATE): is_states_string})

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        states = [
            pypck.lcn_defs.RelayStateModifier[state]
            for state in service.data[CONF_STATE]
        ]

        device_connection = self.get_device_connection(service)
        await device_connection.control_relays(states)


class Led(LcnServiceCall):
    """Set the led state."""

    schema = LcnServiceCall.schema.extend(
        {
            vol.Required(CONF_LED): vol.All(vol.Upper, vol.In(LED_PORTS)),
            vol.Required(CONF_STATE): vol.All(vol.Upper, vol.In(LED_STATUS)),
        }
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        led = pypck.lcn_defs.LedPort[service.data[CONF_LED]]
        led_state = pypck.lcn_defs.LedStatus[service.data[CONF_STATE]]

        device_connection = self.get_device_connection(service)
        await device_connection.control_led(led, led_state)


class VarAbs(LcnServiceCall):
    """Set absolute value of a variable or setpoint.

    Variable has to be set as counter!
    Regulator setpoints can also be set using R1VARSETPOINT, R2VARSETPOINT.
    """

    schema = LcnServiceCall.schema.extend(
        {
            vol.Required(CONF_VARIABLE): vol.All(
                vol.Upper, vol.In(VARIABLES + SETPOINTS)
            ),
            vol.Optional(CONF_VALUE, default=0): vol.Coerce(float),
            vol.Optional(CONF_UNIT_OF_MEASUREMENT, default="native"): vol.All(
                vol.Upper, vol.In(VAR_UNITS)
            ),
        }
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        var = pypck.lcn_defs.Var[service.data[CONF_VARIABLE]]
        value = service.data[CONF_VALUE]
        unit = pypck.lcn_defs.VarUnit.parse(service.data[CONF_UNIT_OF_MEASUREMENT])

        device_connection = self.get_device_connection(service)
        await device_connection.var_abs(var, value, unit)


class VarReset(LcnServiceCall):
    """Reset value of variable or setpoint."""

    schema = LcnServiceCall.schema.extend(
        {vol.Required(CONF_VARIABLE): vol.All(vol.Upper, vol.In(VARIABLES + SETPOINTS))}
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        var = pypck.lcn_defs.Var[service.data[CONF_VARIABLE]]

        device_connection = self.get_device_connection(service)
        await device_connection.var_reset(var)


class VarRel(LcnServiceCall):
    """Shift value of a variable, setpoint or threshold."""

    schema = LcnServiceCall.schema.extend(
        {
            vol.Required(CONF_VARIABLE): vol.All(
                vol.Upper, vol.In(VARIABLES + SETPOINTS + THRESHOLDS)
            ),
            vol.Optional(CONF_VALUE, default=0): vol.Coerce(float),
            vol.Optional(CONF_UNIT_OF_MEASUREMENT, default="native"): vol.All(
                vol.Upper, vol.In(VAR_UNITS)
            ),
            vol.Optional(CONF_RELVARREF, default="current"): vol.All(
                vol.Upper, vol.In(RELVARREF)
            ),
        }
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        var = pypck.lcn_defs.Var[service.data[CONF_VARIABLE]]
        value = service.data[CONF_VALUE]
        unit = pypck.lcn_defs.VarUnit.parse(service.data[CONF_UNIT_OF_MEASUREMENT])
        value_ref = pypck.lcn_defs.RelVarRef[service.data[CONF_RELVARREF]]

        device_connection = self.get_device_connection(service)
        await device_connection.var_rel(var, value, unit, value_ref)


class LockRegulator(LcnServiceCall):
    """Locks a regulator setpoint."""

    schema = LcnServiceCall.schema.extend(
        {
            vol.Required(CONF_SETPOINT): vol.All(vol.Upper, vol.In(SETPOINTS)),
            vol.Optional(CONF_STATE, default=False): bool,
        }
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        setpoint = pypck.lcn_defs.Var[service.data[CONF_SETPOINT]]
        state = service.data[CONF_STATE]

        reg_id = pypck.lcn_defs.Var.to_set_point_id(setpoint)
        device_connection = self.get_device_connection(service)
        await device_connection.lock_regulator(reg_id, state)


class SendKeys(LcnServiceCall):
    """Sends keys (which executes bound commands)."""

    schema = LcnServiceCall.schema.extend(
        {
            vol.Required(CONF_KEYS): vol.All(
                vol.Upper, cv.matches_regex(r"^([A-D][1-8])+$")
            ),
            vol.Optional(CONF_STATE, default="hit"): vol.All(
                vol.Upper, vol.In(SENDKEYCOMMANDS)
            ),
            vol.Optional(CONF_TIME, default=0): cv.positive_int,
            vol.Optional(CONF_TIME_UNIT, default="S"): vol.All(
                vol.Upper, vol.In(TIME_UNITS)
            ),
        }
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        device_connection = self.get_device_connection(service)

        keys = [[False] * 8 for i in range(4)]

        key_strings = zip(
            service.data[CONF_KEYS][::2], service.data[CONF_KEYS][1::2], strict=False
        )

        for table, key in key_strings:
            table_id = ord(table) - 65
            key_id = int(key) - 1
            keys[table_id][key_id] = True

        if (delay_time := service.data[CONF_TIME]) != 0:
            hit = pypck.lcn_defs.SendKeyCommand.HIT
            if pypck.lcn_defs.SendKeyCommand[service.data[CONF_STATE]] != hit:
                raise ValueError(
                    "Only hit command is allowed when sending deferred keys."
                )
            delay_unit = pypck.lcn_defs.TimeUnit.parse(service.data[CONF_TIME_UNIT])
            await device_connection.send_keys_hit_deferred(keys, delay_time, delay_unit)
        else:
            state = pypck.lcn_defs.SendKeyCommand[service.data[CONF_STATE]]
            await device_connection.send_keys(keys, state)


class LockKeys(LcnServiceCall):
    """Lock keys."""

    schema = LcnServiceCall.schema.extend(
        {
            vol.Optional(CONF_TABLE, default="a"): vol.All(
                vol.Upper, cv.matches_regex(r"^[A-D]$")
            ),
            vol.Required(CONF_STATE): is_states_string,
            vol.Optional(CONF_TIME, default=0): cv.positive_int,
            vol.Optional(CONF_TIME_UNIT, default="S"): vol.All(
                vol.Upper, vol.In(TIME_UNITS)
            ),
        }
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        device_connection = self.get_device_connection(service)

        states = [
            pypck.lcn_defs.KeyLockStateModifier[state]
            for state in service.data[CONF_STATE]
        ]
        table_id = ord(service.data[CONF_TABLE]) - 65

        if (delay_time := service.data[CONF_TIME]) != 0:
            if table_id != 0:
                raise ValueError(
                    "Only table A is allowed when locking keys for a specific time."
                )
            delay_unit = pypck.lcn_defs.TimeUnit.parse(service.data[CONF_TIME_UNIT])
            await device_connection.lock_keys_tab_a_temporary(
                delay_time, delay_unit, states
            )
        else:
            await device_connection.lock_keys(table_id, states)

        handler = device_connection.status_requests_handler
        await handler.request_status_locked_keys_timeout()


class DynText(LcnServiceCall):
    """Send dynamic text to LCN-GTxD displays."""

    schema = LcnServiceCall.schema.extend(
        {
            vol.Required(CONF_ROW): vol.All(int, vol.Range(min=1, max=4)),
            vol.Required(CONF_TEXT): vol.All(str, vol.Length(max=60)),
        }
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        row_id = service.data[CONF_ROW] - 1
        text = service.data[CONF_TEXT]

        device_connection = self.get_device_connection(service)
        await device_connection.dyn_text(row_id, text)


class Pck(LcnServiceCall):
    """Send arbitrary PCK command."""

    schema = LcnServiceCall.schema.extend({vol.Required(CONF_PCK): str})

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        pck = service.data[CONF_PCK]
        device_connection = self.get_device_connection(service)
        await device_connection.pck(pck)


class AddressToDeviceId(LcnServiceCall):
    """Get device_id from LCN address string."""

    schema = vol.Schema(
        {
            vol.Required(CONF_ID): cv.positive_int,
            vol.Optional(CONF_SEGMENT_ID, default=0): cv.positive_int,
            vol.Optional(CONF_TYPE, default=CONF_MODULE): vol.Any(
                CONF_MODULE, CONF_GROUP
            ),
            vol.Optional(CONF_HOST, default=None): vol.Any(cv.string, None),
        }
    )
    supports_response = SupportsResponse.ONLY

    async def async_call_service(self, service: ServiceCall) -> JsonObjectType:
        """Execute service call."""
        address: AddressType = (
            service.data[CONF_SEGMENT_ID],
            service.data[CONF_ID],
            service.data[CONF_TYPE] == CONF_GROUP,
        )
        device_id = address_to_device_id(self.hass, address, service.data[CONF_HOST])
        return {CONF_DEVICE_ID: device_id}


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
    ADDRESS_TO_DEVICE_ID = auto()


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
    (LcnService.ADDRESS_TO_DEVICE_ID, AddressToDeviceId),
)


async def register_services(hass: HomeAssistant) -> None:
    """Register services for LCN."""
    for service_name, service in SERVICES:
        hass.services.async_register(
            DOMAIN, service_name, service(hass).async_call_service, service.schema
        )
