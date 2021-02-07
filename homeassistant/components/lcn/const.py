"""Constants for the LCN component."""
from itertools import product

from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
    VOLT,
)

DOMAIN = "lcn"
DATA_LCN = "lcn"
DEFAULT_NAME = "pchk"

CONF_CONNECTIONS = "connections"
CONF_SK_NUM_TRIES = "sk_num_tries"
CONF_OUTPUT = "output"
CONF_DIM_MODE = "dim_mode"
CONF_DIMMABLE = "dimmable"
CONF_TRANSITION = "transition"
CONF_MOTOR = "motor"
CONF_LOCKABLE = "lockable"
CONF_VARIABLE = "variable"
CONF_VALUE = "value"
CONF_RELVARREF = "value_reference"
CONF_SETPOINT = "setpoint"
CONF_LED = "led"
CONF_KEYS = "keys"
CONF_TIME = "time"
CONF_TIME_UNIT = "time_unit"
CONF_TABLE = "table"
CONF_ROW = "row"
CONF_TEXT = "text"
CONF_PCK = "pck"
CONF_CLIMATES = "climates"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_SCENES = "scenes"
CONF_REGISTER = "register"
CONF_OUTPUTS = "outputs"
CONF_REVERSE_TIME = "reverse_time"

DIM_MODES = ["STEPS50", "STEPS200"]

OUTPUT_PORTS = ["OUTPUT1", "OUTPUT2", "OUTPUT3", "OUTPUT4"]

RELAY_PORTS = [
    "RELAY1",
    "RELAY2",
    "RELAY3",
    "RELAY4",
    "RELAY5",
    "RELAY6",
    "RELAY7",
    "RELAY8",
    "MOTORONOFF1",
    "MOTORUPDOWN1",
    "MOTORONOFF2",
    "MOTORUPDOWN2",
    "MOTORONOFF3",
    "MOTORUPDOWN3",
    "MOTORONOFF4",
    "MOTORUPDOWN4",
]

MOTOR_PORTS = ["MOTOR1", "MOTOR2", "MOTOR3", "MOTOR4", "OUTPUTS"]

LED_PORTS = [
    "LED1",
    "LED2",
    "LED3",
    "LED4",
    "LED5",
    "LED6",
    "LED7",
    "LED8",
    "LED9",
    "LED10",
    "LED11",
    "LED12",
]

LED_STATUS = ["OFF", "ON", "BLINK", "FLICKER"]

LOGICOP_PORTS = ["LOGICOP1", "LOGICOP2", "LOGICOP3", "LOGICOP4"]

BINSENSOR_PORTS = [
    "BINSENSOR1",
    "BINSENSOR2",
    "BINSENSOR3",
    "BINSENSOR4",
    "BINSENSOR5",
    "BINSENSOR6",
    "BINSENSOR7",
    "BINSENSOR8",
]

KEYS = [f"{t[0]:s}{t[1]:d}" for t in product(["A", "B", "C", "D"], range(1, 9))]

VARIABLES = [
    "VAR1ORTVAR",
    "VAR2ORR1VAR",
    "VAR3ORR2VAR",
    "TVAR",
    "R1VAR",
    "R2VAR",
    "VAR1",
    "VAR2",
    "VAR3",
    "VAR4",
    "VAR5",
    "VAR6",
    "VAR7",
    "VAR8",
    "VAR9",
    "VAR10",
    "VAR11",
    "VAR12",
]

SETPOINTS = ["R1VARSETPOINT", "R2VARSETPOINT"]

THRESHOLDS = [
    "THRS1",
    "THRS2",
    "THRS3",
    "THRS4",
    "THRS5",
    "THRS2_1",
    "THRS2_2",
    "THRS2_3",
    "THRS2_4",
    "THRS3_1",
    "THRS3_2",
    "THRS3_3",
    "THRS3_4",
    "THRS4_1",
    "THRS4_2",
    "THRS4_3",
    "THRS4_4",
]

S0_INPUTS = ["S0INPUT1", "S0INPUT2", "S0INPUT3", "S0INPUT4"]

VAR_UNITS = [
    "",
    "LCN",
    "NATIVE",
    TEMP_CELSIUS,
    TEMP_KELVIN,
    TEMP_FAHRENHEIT,
    "LUX_T",
    "LX_T",
    "LUX_I",
    "LUX",
    "LX",
    "M/S",
    "METERPERSECOND",
    PERCENTAGE,
    "PERCENT",
    "PPM",
    "VOLT",
    VOLT,
    "AMPERE",
    "AMP",
    "A",
    "DEGREE",
    DEGREE,
]

RELVARREF = ["CURRENT", "PROG"]

SENDKEYCOMMANDS = ["HIT", "MAKE", "BREAK", "DONTSEND"]

TIME_UNITS = [
    "SECONDS",
    "SECOND",
    "SEC",
    "S",
    "MINUTES",
    "MINUTE",
    "MIN",
    "M",
    "HOURS",
    "HOUR",
    "H",
    "DAYS",
    "DAY",
    "D",
]

MOTOR_REVERSE_TIME = ["RT70", "RT600", "RT1200"]
