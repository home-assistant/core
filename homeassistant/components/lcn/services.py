"""Service related dependencies for LCN component."""
import voluptuous as vol

from homeassistant.const import (
    CONF_BRIGHTNESS, CONF_STATE, CONF_UNIT_OF_MEASUREMENT)
import homeassistant.helpers.config_validation as cv

from ..lcn import DATA_LCN, LIB_LCN
from .core import (
    CONF_ADDRESS, CONF_CONNECTIONS, CONF_KEYS, CONF_LED, CONF_OUTPUT, CONF_PCK,
    CONF_RELVARREF, CONF_ROW, CONF_SETPOINT, CONF_TABLE, CONF_TEXT, CONF_TIME,
    CONF_TIME_UNIT, CONF_TRANSITION, CONF_VALUE, CONF_VARIABLE, LED_PORTS,
    LED_STATUS, OUTPUT_PORTS, RELVARREF, SENDKEYCOMMANDS, SETPOINTS,
    THRESHOLDS, TIME_UNITS, VAR_UNITS, VARIABLES, get_connection, is_address,
    is_key_lock_states_string, is_relays_states_string)


class LcnServiceCall():
    """Parent class for all LCN service calls."""

    schema = vol.Schema({
        vol.Required(CONF_ADDRESS): is_address
        })

    def __init__(self, hass):
        """Initialize service call."""
        self.pypck = hass.data[DATA_LCN][LIB_LCN]
        self.connections = hass.data[DATA_LCN][CONF_CONNECTIONS]

    def get_address_connection(self, call):
        """Get address connection object."""
        addr, connection_id = call.data[CONF_ADDRESS]
        addr = self.pypck.lcn_addr.LcnAddr(*addr)
        if connection_id is None:
            connection = self.connections[0]
        else:
            connection = get_connection(self.connections, connection_id)

        return connection.get_address_conn(addr)


class OutputAbs(LcnServiceCall):
    """Set absolute brightness of output port in percent.

    Example:
    {"address": "myhome.0.7", "output": "output1", "brightness": 100,
     "transition": 0}
    """

    schema = LcnServiceCall.schema.extend({
        vol.Required(CONF_OUTPUT): vol.Any(*OUTPUT_PORTS),
        vol.Required(CONF_BRIGHTNESS):
            vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional(CONF_TRANSITION, default=0):
            vol.All(vol.Coerce(float), vol.Range(min=0., max=486.))
        })

    def __call__(self, call):
        """Execute service call."""
        output = self.pypck.lcn_defs.OutputPort[call.data[CONF_OUTPUT].upper()]
        brightness = call.data[CONF_BRIGHTNESS]
        transition = self.pypck.lcn_defs.time_to_ramp_value(
            call.data[CONF_TRANSITION] * 1000)

        address_connection = self.get_address_connection(call)
        address_connection.dim_output(output.value, brightness, transition)


class OutputRel(LcnServiceCall):
    """Set relative brightness of output port in percent.

    Example:
    {"address": "myhome.0.7", "output": "output1", "brightness": 30}
    """

    schema = LcnServiceCall.schema.extend({
        vol.Required(CONF_OUTPUT): vol.Any(*OUTPUT_PORTS),
        vol.Required(CONF_BRIGHTNESS):
            vol.All(vol.Coerce(int), vol.Range(min=-100, max=100))
        })

    def __call__(self, call):
        """Execute service call."""
        output = self.pypck.lcn_defs.OutputPort[call.data[CONF_OUTPUT].upper()]
        brightness = call.data[CONF_BRIGHTNESS]

        address_connection = self.get_address_connection(call)
        address_connection.rel_output(output.value, brightness)


class OutputToggle(LcnServiceCall):
    """Toggle output port.

    Example:
    {"address": "myhome.0.7", "output": "output1", "transition": 0}
    """

    schema = LcnServiceCall.schema.extend({
        vol.Required(CONF_OUTPUT): vol.Any(*OUTPUT_PORTS),
        vol.Optional(CONF_TRANSITION, default=0):
            vol.All(vol.Coerce(float), vol.Range(min=0., max=486.))
        })

    def __call__(self, call):
        """Execute service call."""
        output = self.pypck.lcn_defs.OutputPort[call.data[CONF_OUTPUT].upper()]
        transition = self.pypck.lcn_defs.time_to_ramp_value(
            call.data[CONF_TRANSITION] * 1000)

        address_connection = self.get_address_connection(call)
        address_connection.toggle_output(output.value, transition)


class Relays(LcnServiceCall):
    """Set the relays status.

    Example:
    {"address": "myhome.0.7", "state": "t---001-"}
    """

    schema = LcnServiceCall.schema.extend({
        vol.Required(CONF_STATE): is_relays_states_string})

    def __call__(self, call):
        """Execute service call."""
        states = [self.pypck.lcn_defs.RelayStateModifier[state]
                  for state in call.data[CONF_STATE]]

        address_connection = self.get_address_connection(call)
        address_connection.control_relays(states)


class Led(LcnServiceCall):
    """Set the led state.

    Example:
    {"address": "myhome.0.7", "led": "led6", "state": "blink"}
    """

    schema = LcnServiceCall.schema.extend({
        vol.Required(CONF_LED): vol.Any(*LED_PORTS),
        vol.Required(CONF_STATE): vol.Any(*LED_STATUS)})

    def __call__(self, call):
        """Execute service call."""
        led = self.pypck.lcn_defs.LedPort[call.data[CONF_LED].upper()]
        led_state = self.pypck.lcn_defs.LedStatus[
            call.data[CONF_STATE].upper()]

        address_connection = self.get_address_connection(call)
        address_connection.control_led(led, led_state)


class VarAbs(LcnServiceCall):
    """Set absolute value of a variable or setpoint.

    Variable has to be set as counter!
    Reguator setpoints can also be set using R1VARSETPOINT, R2VARSETPOINT.
    Template for a service call:

    Example:
    {"address": "myhome.0.7", "variable": "var1", "value": 75,
     "unit_of_measurement": "%"}
    """

    schema = LcnServiceCall.schema.extend({
        vol.Required(CONF_VARIABLE): vol.Any(*(VARIABLES + SETPOINTS)),
        vol.Optional(CONF_VALUE, default=0):
            vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT, default='native'):
            vol.Any(*VAR_UNITS)
        })

    def __call__(self, call):
        """Execute service call."""
        var = self.pypck.lcn_defs.Var[call.data[CONF_VARIABLE].upper()]
        value = call.data[CONF_VALUE]
        unit = self.pypck.lcn_defs.VarUnit.parse(
            call.data[CONF_UNIT_OF_MEASUREMENT].upper())

        address_connection = self.get_address_connection(call)
        address_connection.var_abs(var, value, unit)


class VarReset(LcnServiceCall):
    """Reset value of variable or setpoint.

    Example:
    {"address": "myhome.0.7", "variable": "var1"}
    """

    schema = LcnServiceCall.schema.extend({
        vol.Required(CONF_VARIABLE): vol.Any(*(VARIABLES + SETPOINTS))
        })

    def __call__(self, call):
        """Execute service call."""
        var = self.pypck.lcn_defs.Var[call.data[CONF_VARIABLE].upper()]

        address_connection = self.get_address_connection(call)
        address_connection.var_reset(var)


class VarRel(LcnServiceCall):
    """Shift value of a variable, setpoint or threshold.

    Example:
    {"address": "myhome.0.7", "variable": "var1", "value": 10,
     "unit_of_measurement": "%"}
    """

    schema = LcnServiceCall.schema.extend({
        vol.Required(CONF_VARIABLE):
            vol.Any(*(VARIABLES + SETPOINTS + THRESHOLDS)),
        vol.Optional(CONF_VALUE, default=0): int,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT, default='native'):
            vol.Any(*VAR_UNITS),
        vol.Optional(CONF_RELVARREF, default='current'): vol.Any(*RELVARREF)
        })

    def __call__(self, call):
        """Execute service call."""
        var = self.pypck.lcn_defs.Var[call.data[CONF_VARIABLE].upper()]
        value = call.data[CONF_VALUE]
        unit = self.pypck.lcn_defs.VarUnit.parse(
            call.data[CONF_UNIT_OF_MEASUREMENT].upper())
        value_ref = self.pypck.lcn_defs.RelVarRef[
            call.data[CONF_RELVARREF].upper()]

        address_connection = self.get_address_connection(call)
        address_connection.var_rel(var, value, unit, value_ref)


class LockRegulator(LcnServiceCall):
    """Locks a regulator setpoint.

    Example:
    {"address": "myhome.0.7", "setpoint": "r1varsetpoint", "state": true}
    """

    schema = LcnServiceCall.schema.extend({
        vol.Required(CONF_SETPOINT): vol.Any(*SETPOINTS),
        vol.Optional(CONF_STATE, default=False): bool,
        })

    def __call__(self, call):
        """Execute service call."""
        setpoint = self.pypck.lcn_defs.Var[call.data[CONF_SETPOINT].upper()]
        state = call.data[CONF_STATE]

        reg_id = self.pypck.lcn_defs.Var.to_set_point_id(setpoint)
        address_connection = self.get_address_connection(call)
        address_connection.lock_regulator(reg_id, state)


class SendKeys(LcnServiceCall):
    """Sends keys (which executes bound commands).

    Example:
    {"address": "myhome.0.7", "keys": "a1a5d8", "state": "hit"}
    {"address": "myhome.0.7", "keys": "a1a5d8", "time": 5, "time_unit": "s"}
    """

    schema = LcnServiceCall.schema.extend({
        vol.Required(CONF_KEYS): cv.matches_regex(r'^([a-dA-D][1-8])+$'),
        vol.Optional(CONF_STATE, default='hit'): vol.Any(*SENDKEYCOMMANDS),
        vol.Optional(CONF_TIME, default=0): vol.All(int, vol.Range(min=0)),
        vol.Optional(CONF_TIME_UNIT, default='s'): vol.Any(*TIME_UNITS),
        })

    def __call__(self, call):
        """Execute service call."""
        address_connection = self.get_address_connection(call)

        keys = [[False] * 8 for i in range(4)]

        key_strings = zip(call.data[CONF_KEYS][::2],
                          call.data[CONF_KEYS][1::2])

        for table, key in key_strings:
            table_id = ord(table.upper()) - 65
            key_id = int(key) - 1
            keys[table_id][key_id] = True

        delay_time = call.data[CONF_TIME]
        if delay_time != 0:
            hit = self.pypck.lcn_defs.SendKeyCommand.HIT
            if self.pypck.lcn_defs.SendKeyCommand[
                    call.data[CONF_STATE].upper()] != hit:
                raise ValueError('Only hit command is allowed when sending'
                                 ' deferred keys.')
            delay_unit = self.pypck.lcn_defs.TimeUnit.parse(
                call.data[CONF_TIME_UNIT].upper())
            address_connection.send_keys_hit_deferred(
                keys, delay_time, delay_unit)
        else:
            state = self.pypck.lcn_defs.SendKeyCommand[
                call.data[CONF_STATE].upper()]
            address_connection.send_keys(keys, state)


class LockKeys(LcnServiceCall):
    """Lock keys.

    Example:
    {"address": "myhome.0.7", "table": "a", "state": "1---t0--"}
    {"address": "myhome.0.7", "state": "1---t0--", "time": 10,
     "time_unit": "s"}
    """

    schema = LcnServiceCall.schema.extend({
        vol.Optional(CONF_TABLE, default='a'): cv.matches_regex(r'^[a-dA-D]$'),
        vol.Required(CONF_STATE): is_key_lock_states_string,
        vol.Optional(CONF_TIME, default=0): vol.All(int, vol.Range(min=0)),
        vol.Optional(CONF_TIME_UNIT, default='s'): vol.Any(*TIME_UNITS),
        })

    def __call__(self, call):
        """Execute service call."""
        address_connection = self.get_address_connection(call)

        states = [self.pypck.lcn_defs.KeyLockStateModifier[state]
                  for state in call.data[CONF_STATE]]
        table_id = ord(call.data[CONF_TABLE].upper()) - 65

        delay_time = call.data[CONF_TIME]
        if delay_time != 0:
            if table_id != 0:
                raise ValueError('Only table A is allowed when locking keys'
                                 ' for a specific time.')
            delay_unit = self.pypck.lcn_defs.TimeUnit.parse(
                call.data[CONF_TIME_UNIT].upper())
            address_connection.lock_keys_tab_a_temporary(
                delay_time, delay_unit, states)
        else:
            address_connection.lock_keys(table_id, states)

        address_connection.request_status_locked_keys_timeout()


class DynText(LcnServiceCall):
    """Send dynamic text to LCN-GTxD displays.

    Example:
    {"address": "myhome.0.7", "row": 1, "text": "text in row 1"}
    """

    schema = LcnServiceCall.schema.extend({
        vol.Required(CONF_ROW): vol.All(int, vol.Range(min=1, max=4)),
        vol.Required(CONF_TEXT): vol.All(str, vol.Length(max=60))
        })

    def __call__(self, call):
        """Execute service call."""
        row_id = call.data[CONF_ROW] - 1
        text = call.data[CONF_TEXT]

        address_connection = self.get_address_connection(call)
        address_connection.dyn_text(row_id, text)


class Pck(LcnServiceCall):
    """Send arbitrary PCK command.

    Example:
    {"address": "myhome.0.7", "pck": "PIN4"}
    """

    schema = LcnServiceCall.schema.extend({
        vol.Required(CONF_PCK): str
        })

    def __call__(self, call):
        """Execute service call."""
        pck = call.data[CONF_PCK]
        address_connection = self.get_address_connection(call)
        address_connection.pck(pck)
