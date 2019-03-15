"""Constants for the LCN component."""
import re

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

DIM_MODES = ['STEPS50', 'STEPS200']
OUTPUT_PORTS = ['OUTPUT1', 'OUTPUT2', 'OUTPUT3', 'OUTPUT4']
RELAY_PORTS = ['RELAY1', 'RELAY2', 'RELAY3', 'RELAY4',
               'RELAY5', 'RELAY6', 'RELAY7', 'RELAY8',
               'MOTORONOFF1', 'MOTORUPDOWN1', 'MOTORONOFF2', 'MOTORUPDOWN2',
               'MOTORONOFF3', 'MOTORUPDOWN3', 'MOTORONOFF4', 'MOTORUPDOWN4']
MOTOR_PORTS = ['MOTOR1', 'MOTOR2', 'MOTOR3', 'MOTOR4']
