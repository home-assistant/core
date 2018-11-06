"""Core dependencies for LCN component."""
from itertools import product
import re

import voluptuous as vol

# definitions
CONF_SEGMENT_ID = 'segment_id'
CONF_SK_NUM_TRIES = 'sk_num_tries'
CONF_DIM_MODE = 'dim_mode'
CONF_OUTPUT = 'output'
CONF_TRANSITION = 'transition'
CONF_DIMMABLE = 'dimmable'
CONF_MOTOR = 'motor'
CONF_CONNECTIONS = 'connections'
CONF_ADDRESS = 'address'
CONF_VARIABLE = 'variable'
CONF_VALUE = 'value'
CONF_RELVARREF = 'value_reference'
CONF_SOURCE = 'source'
CONF_SETPOINT = 'setpoint'
CONF_LED = 'led'
CONF_KEYS = 'keys'
CONF_TIME = 'time'
CONF_TIME_UNIT = 'time_unit'
CONF_TABLE = 'table'
CONF_ROW = 'row'
CONF_TEXT = 'text'
CONF_PCK = 'pck'

DIM_MODES = ['steps50', 'steps200']
OUTPUT_PORTS = ['output1', 'output2', 'output3', 'output4']
RELAY_PORTS = ['relay1', 'relay2', 'relay3', 'relay4',
               'relay5', 'relay6', 'relay7', 'relay8',
               'motoronoff1', 'motorupdown1', 'motoronoff2', 'motorupdown2',
               'motoronoff3', 'motorupdown3', 'motoronoff4', 'motorupdown4']
MOTOR_PORTS = ['motor1', 'motor2', 'motor3', 'motor4']
LED_PORTS = ['led1', 'led2', 'led3', 'led4', 'led5', 'led6',
             'led7', 'led8', 'led9', 'led10', 'led11', 'led12']
LED_STATUS = ['off', 'on', 'blink', 'flicker']
LOGICOP_PORTS = ['logicop1', 'logicop2', 'logicop3', 'logicop4']
LOGICOP_STATUS = ['not', 'or', 'and']

BINSENSOR_PORTS = ['binsensor1', 'binsensor2', 'binsensor3', 'binsensor4',
                   'binsensor5', 'binsensor6', 'binsensor7', 'binsensor8']

KEYS = ['{:s}{:d}'.format(t[0], t[1]) for t in product(['a', 'b', 'c', 'd'],
                                                       range(1, 9))]

VARIABLES = ['var1ortvar', 'var2orr1var', 'var3orr2var',
             'tvar', 'r1var', 'r2var',
             'var1', 'var2', 'var3', 'var4', 'var5', 'var6',
             'var7', 'var8', 'var9', 'var10', 'var11', 'var12']

SETPOINTS = ['r1varsetpoint', 'r2varsetpoint']

THRESHOLDS = ['thrs1', 'thrs2', 'thrs3', 'thrs4', 'thrs5',
              'thrs2_1', 'thrs2_2', 'thrs2_3', 'thrs2_4',
              'thrs3_1', 'thrs3_2', 'thrs3_3', 'thrs3_4',
              'thrs4_1', 'thrs4_2', 'thrs4_3', 'thrs4_4']

S0_INPUTS = ['s0input1', 's0input2', 's0input3', 's0input4']

VAR_UNITS = ['', 'lcn', 'native',
             'celsius', '\u00b0celsius', '\u00b0c',
             'kelvin', '\u00b0kelvin', '\u00b0k',
             'fahrenheit', '\u00b0fahrenheit', '\u00b0f'
             'lux_t', 'lx_t',
             'lux_i', 'lux', 'lx',
             'm/s', 'meterpersecond',
             '%', 'percent',
             'ppm',
             'volt', 'v',
             'ampere', 'amp', 'a',
             'degree', '\u00b0']

RELVARREF = ['current', 'prog']

SENDKEYCOMMANDS = ['hit', 'make', 'break', 'dontsend']

TIME_UNITS = ['seconds', 'second', 'sec', 's',
              'minutes', 'minute', 'min', 'm',
              'hours', 'hour', 'h',
              'days', 'day', 'd']

# Regex
PATTERN_ADDRESS = re.compile('^((?P<conn_id>\\w+)\\.)?s?(?P<seg_id>\\d+)'
                             '\\.(?P<type>m|g)?(?P<id>\\d+)$')


def get_connection(connections, connection_id):
    """Return the connection object from list."""
    for connection in connections:
        if connection.connection_id == connection_id:
            return connection
    raise ValueError('Unknown connection_id.')


# Validators
def is_address(value):
    """Validate the given address string.

    Valid address strings:

    Examples for S000M005 at myhome:
        myhome.s000.m005
        myhome.s0.m5
        myhome.0.5    ("m" is implicit if missing)

    Examples for s000g011
        myhome.0.g11
        myhome.s0.g11
    """
    matcher = PATTERN_ADDRESS.match(value)
    if matcher:
        is_group = (matcher.group('type') == 'g')
        addr = (int(matcher.group('seg_id')),
                int(matcher.group('id')),
                is_group)
        conn_id = matcher.group('conn_id')
        return addr, conn_id
    raise vol.error.Invalid('Not a valid address string.')


def is_relays_states_string(states_string):
    """Validate the given states string and return states list."""
    states_string = states_string.upper()
    if len(states_string) == 8:
        states = []
        for state_string in states_string:
            if state_string == '1':
                state = 'ON'
            elif state_string == '0':
                state = 'OFF'
            elif state_string == 'T':
                state = 'TOGGLE'
            elif state_string == '-':
                state = 'NOCHANGE'
            else:
                raise vol.error.Invalid('Not a valid relay state string.')
            states.append(state)
        return states
    raise vol.error.Invalid('Wrong length of relay state string.')


def is_key_lock_states_string(states_string):
    """Validate the given states string and returns states list."""
    states_string = states_string.upper()
    if len(states_string) == 8:
        states = []
        for state_string in states_string:
            if state_string == '1':
                state = 'ON'
            elif state_string == '0':
                state = 'OFF'
            elif state_string == 'T':
                state = 'TOGGLE'
            elif state_string == '-':
                state = 'NOCHANGE'
            else:
                raise vol.error.Invalid('Not a valid key lock state string.')
            states.append(state)
        return states
    raise vol.error.Invalid('Wrong length of key lock state string.')
