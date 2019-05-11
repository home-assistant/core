# coding: utf-8
"""Constants for the LCN component."""
from itertools import product
import re

import voluptuous as vol

from homeassistant.const import CONF_NAME, TEMP_CELSIUS, TEMP_FAHRENHEIT

DOMAIN = 'lcn'
DATA_LCN = 'lcn'
DEFAULT_NAME = 'pchk'

# Regex for address validation
PATTERN_ADDRESS = re.compile('^((?P<conn_id>\\w+)\\.)?s?(?P<seg_id>\\d+)'
                             '\\.(?P<type>m|g)?(?P<id>\\d+)$')

CONF_CONNECTIONS = 'connections'
CONF_SK_NUM_TRIES = 'sk_num_tries'
CONF_OUTPUT = 'output'
CONF_DIM_MODE = 'dim_mode'
CONF_DIMMABLE = 'dimmable'
CONF_TRANSITION = 'transition'
CONF_MOTOR = 'motor'
CONF_SOURCE = 'source'
CONF_SETPOINT = 'setpoint'
CONF_LOCKABLE = 'lockable'
CONF_CLIMATES = 'climates'
CONF_MAX_TEMP = 'max_temp'
CONF_MIN_TEMP = 'min_temp'

DIM_MODES = ['STEPS50', 'STEPS200']

OUTPUT_PORTS = ['OUTPUT1', 'OUTPUT2', 'OUTPUT3', 'OUTPUT4']

RELAY_PORTS = ['RELAY1', 'RELAY2', 'RELAY3', 'RELAY4',
               'RELAY5', 'RELAY6', 'RELAY7', 'RELAY8',
               'MOTORONOFF1', 'MOTORUPDOWN1', 'MOTORONOFF2', 'MOTORUPDOWN2',
               'MOTORONOFF3', 'MOTORUPDOWN3', 'MOTORONOFF4', 'MOTORUPDOWN4']

MOTOR_PORTS = ['MOTOR1', 'MOTOR2', 'MOTOR3', 'MOTOR4']

LED_PORTS = ['LED1', 'LED2', 'LED3', 'LED4', 'LED5', 'LED6',
             'LED7', 'LED8', 'LED9', 'LED10', 'LED11', 'LED12']

LOGICOP_PORTS = ['LOGICOP1', 'LOGICOP2', 'LOGICOP3', 'LOGICOP4']

BINSENSOR_PORTS = ['BINSENSOR1', 'BINSENSOR2', 'BINSENSOR3', 'BINSENSOR4',
                   'BINSENSOR5', 'BINSENSOR6', 'BINSENSOR7', 'BINSENSOR8']

KEYS = ['{:s}{:d}'.format(t[0], t[1]) for t in product(['A', 'B', 'C', 'D'],
                                                       range(1, 9))]

VARIABLES = ['VAR1ORTVAR', 'VAR2ORR1VAR', 'VAR3ORR2VAR',
             'TVAR', 'R1VAR', 'R2VAR',
             'VAR1', 'VAR2', 'VAR3', 'VAR4', 'VAR5', 'VAR6',
             'VAR7', 'VAR8', 'VAR9', 'VAR10', 'VAR11', 'VAR12']

SETPOINTS = ['R1VARSETPOINT', 'R2VARSETPOINT']

THRESHOLDS = ['THRS1', 'THRS2', 'THRS3', 'THRS4', 'THRS5',
              'THRS2_1', 'THRS2_2', 'THRS2_3', 'THRS2_4',
              'THRS3_1', 'THRS3_2', 'THRS3_3', 'THRS3_4',
              'THRS4_1', 'THRS4_2', 'THRS4_3', 'THRS4_4']

S0_INPUTS = ['S0INPUT1', 'S0INPUT2', 'S0INPUT3', 'S0INPUT4']

VAR_UNITS = ['', 'LCN', 'NATIVE',
             TEMP_CELSIUS,
             '°K',
             TEMP_FAHRENHEIT,
             'LUX_T', 'LX_T',
             'LUX_I', 'LUX', 'LX',
             'M/S', 'METERPERSECOND',
             '%', 'PERCENT',
             'PPM',
             'VOLT', 'V',
             'AMPERE', 'AMP', 'A',
             'DEGREE', '°']


def get_connection(connections, connection_id=None):
    """Return the connection object from list."""
    if connection_id is None:
        connection = connections[0]
    else:
        for connection in connections:
            if connection.connection_id == connection_id:
                break
        else:
            raise ValueError('Unknown connection_id.')
    return connection


def has_unique_connection_names(connections):
    """Validate that all connection names are unique.

    Use 'pchk' as default connection_name (or add a numeric suffix if
    pchk' is already in use.
    """
    for suffix, connection in enumerate(connections):
        connection_name = connection.get(CONF_NAME)
        if connection_name is None:
            if suffix == 0:
                connection[CONF_NAME] = DEFAULT_NAME
            else:
                connection[CONF_NAME] = '{}{:d}'.format(DEFAULT_NAME, suffix)

    schema = vol.Schema(vol.Unique())
    schema([connection.get(CONF_NAME) for connection in connections])
    return connections


def is_address(value):
    """Validate the given address string.

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
