"""Constants used in modbus integration."""

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate.const import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_COVERS,
    CONF_LIGHTS,
    CONF_SENSORS,
    CONF_SWITCHES,
)

# configuration names
CONF_BAUDRATE = "baudrate"
CONF_BYTESIZE = "bytesize"
CONF_CLIMATES = "climates"
CONF_CLOSE_COMM_ON_ERROR = "close_comm_on_error"
CONF_COILS = "coils"
CONF_CURRENT_TEMP = "current_temp_register"
CONF_CURRENT_TEMP_REGISTER_TYPE = "current_temp_register_type"
CONF_DATA_COUNT = "data_count"
CONF_DATA_TYPE = "data_type"
CONF_FANS = "fans"
CONF_HUB = "hub"
CONF_INPUTS = "inputs"
CONF_INPUT_TYPE = "input_type"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_MSG_WAIT = "message_wait_milliseconds"
CONF_PARITY = "parity"
CONF_REGISTER = "register"
CONF_REGISTER_TYPE = "register_type"
CONF_REGISTERS = "registers"
CONF_RETRIES = "retries"
CONF_RETRY_ON_EMPTY = "retry_on_empty"
CONF_REVERSE_ORDER = "reverse_order"
CONF_PRECISION = "precision"
CONF_RTUOVERTCP = "rtuovertcp"
CONF_SCALE = "scale"
CONF_SERIAL = "serial"
CONF_STATE_CLOSED = "state_closed"
CONF_STATE_CLOSING = "state_closing"
CONF_STATE_OFF = "state_off"
CONF_STATE_ON = "state_on"
CONF_STATE_OPEN = "state_open"
CONF_STATE_OPENING = "state_opening"
CONF_STATUS_REGISTER = "status_register"
CONF_STATUS_REGISTER_TYPE = "status_register_type"
CONF_STEP = "temp_step"
CONF_STOPBITS = "stopbits"
CONF_SWAP = "swap"
CONF_SWAP_BYTE = "byte"
CONF_SWAP_NONE = "none"
CONF_SWAP_WORD = "word"
CONF_SWAP_WORD_BYTE = "word_byte"
CONF_TARGET_TEMP = "target_temp_register"
CONF_TCP = "tcp"
CONF_UDP = "udp"
CONF_VERIFY = "verify"
CONF_VERIFY_REGISTER = "verify_register"
CONF_VERIFY_STATE = "verify_state"
CONF_WRITE_TYPE = "write_type"

# service call attributes
ATTR_ADDRESS = "address"
ATTR_HUB = "hub"
ATTR_UNIT = "unit"
ATTR_VALUE = "value"
ATTR_STATE = "state"
ATTR_TEMPERATURE = "temperature"

# data types
DATA_TYPE_CUSTOM = "custom"
DATA_TYPE_FLOAT = "float"
DATA_TYPE_INT = "int"
DATA_TYPE_UINT = "uint"
DATA_TYPE_STRING = "string"
DATA_TYPE_INT16 = "int16"
DATA_TYPE_INT32 = "int32"
DATA_TYPE_INT64 = "int64"
DATA_TYPE_UINT16 = "uint16"
DATA_TYPE_UINT32 = "uint32"
DATA_TYPE_UINT64 = "uint64"
DATA_TYPE_FLOAT16 = "float16"
DATA_TYPE_FLOAT32 = "float32"
DATA_TYPE_FLOAT64 = "float64"

# call types
CALL_TYPE_COIL = "coil"
CALL_TYPE_DISCRETE = "discrete_input"
CALL_TYPE_REGISTER_HOLDING = "holding"
CALL_TYPE_REGISTER_INPUT = "input"
CALL_TYPE_WRITE_COIL = "write_coil"
CALL_TYPE_WRITE_COILS = "write_coils"
CALL_TYPE_WRITE_REGISTER = "write_register"
CALL_TYPE_WRITE_REGISTERS = "write_registers"
CALL_TYPE_X_COILS = "coils"
CALL_TYPE_X_REGISTER_HOLDINGS = "holdings"

# service calls
SERVICE_WRITE_COIL = "write_coil"
SERVICE_WRITE_REGISTER = "write_register"

# integration names
DEFAULT_HUB = "modbus_hub"
DEFAULT_SCAN_INTERVAL = 15  # seconds
DEFAULT_SLAVE = 1
DEFAULT_STRUCTURE_PREFIX = ">f"
DEFAULT_STRUCT_FORMAT = {
    DATA_TYPE_INT16: ["h", 1],
    DATA_TYPE_INT32: ["i", 2],
    DATA_TYPE_INT64: ["q", 4],
    DATA_TYPE_UINT16: ["H", 1],
    DATA_TYPE_UINT32: ["I", 2],
    DATA_TYPE_UINT64: ["Q", 4],
    DATA_TYPE_FLOAT16: ["e", 1],
    DATA_TYPE_FLOAT32: ["f", 2],
    DATA_TYPE_FLOAT64: ["d", 4],
    DATA_TYPE_STRING: ["s", 1],
}
DEFAULT_TEMP_UNIT = "C"
MODBUS_DOMAIN = "modbus"

PLATFORMS = (
    (BINARY_SENSOR_DOMAIN, CONF_BINARY_SENSORS),
    (CLIMATE_DOMAIN, CONF_CLIMATES),
    (COVER_DOMAIN, CONF_COVERS),
    (LIGHT_DOMAIN, CONF_LIGHTS),
    (FAN_DOMAIN, CONF_FANS),
    (SENSOR_DOMAIN, CONF_SENSORS),
    (SWITCH_DOMAIN, CONF_SWITCHES),
)
