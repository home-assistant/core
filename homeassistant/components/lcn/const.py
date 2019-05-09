# coding: utf-8
"""Constants for the LCN component."""
from itertools import product
import re

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT

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
