"""Constants used in modbus integration."""

# configuration names
CONF_BAUDRATE = "baudrate"
CONF_BINARY_SENSOR = "binary_sensor"
CONF_BYTESIZE = "bytesize"
CONF_CLIMATE = "climate"
CONF_CLIMATES = "climates"
CONF_COILS = "coils"
CONF_COVER = "cover"
CONF_CURRENT_TEMP = "current_temp_register"
CONF_CURRENT_TEMP_REGISTER_TYPE = "current_temp_register_type"
CONF_DATA_COUNT = "data_count"
CONF_DATA_TYPE = "data_type"
CONF_HUB = "hub"
CONF_INPUTS = "inputs"
CONF_INPUT_TYPE = "input_type"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_PARITY = "parity"
CONF_REGISTER = "register"
CONF_REGISTER_TYPE = "register_type"
CONF_REGISTERS = "registers"
CONF_REVERSE_ORDER = "reverse_order"
CONF_PRECISION = "precision"
CONF_SCALE = "scale"
CONF_SENSOR = "sensor"
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
CONF_SWITCH = "switch"
CONF_TARGET_TEMP = "target_temp_register"
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

# call types
CALL_TYPE_COIL = "coil"
CALL_TYPE_DISCRETE = "discrete_input"
CALL_TYPE_REGISTER_HOLDING = "holding"
CALL_TYPE_REGISTER_INPUT = "input"

# service calls
SERVICE_WRITE_COIL = "write_coil"
SERVICE_WRITE_REGISTER = "write_register"

# integration names
DEFAULT_HUB = "modbus_hub"
DEFAULT_SCAN_INTERVAL = 15  # seconds
DEFAULT_SLAVE = 1
DEFAULT_STRUCTURE_PREFIX = ">f"
DEFAULT_STRUCT_FORMAT = {
    DATA_TYPE_INT: {1: "h", 2: "i", 4: "q"},
    DATA_TYPE_UINT: {1: "H", 2: "I", 4: "Q"},
    DATA_TYPE_FLOAT: {1: "e", 2: "f", 4: "d"},
}
DEFAULT_TEMP_UNIT = "C"
MODBUS_DOMAIN = "modbus"
