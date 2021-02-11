"""Constants used in modbus integration."""

# configuration names
CONF_BAUDRATE = "baudrate"
CONF_BYTESIZE = "bytesize"
CONF_HUB = "hub"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"
CONF_REGISTER = "register"
CONF_REGISTER_TYPE = "register_type"
CONF_REGISTERS = "registers"
CONF_REVERSE_ORDER = "reverse_order"
CONF_SCALE = "scale"
CONF_COUNT = "count"
CONF_PRECISION = "precision"
CONF_COILS = "coils"

# integration names
DEFAULT_HUB = "default"
MODBUS_DOMAIN = "modbus"

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

# the following constants are TBD.
# changing those in general causes a breaking change, because
# the contents of configuration.yaml needs to be updated,
# therefore they are left to a later date.
# but kept here, with a reference to the file using them.

# __init.py
ATTR_ADDRESS = "address"
ATTR_HUB = "hub"
ATTR_UNIT = "unit"
ATTR_VALUE = "value"
SERVICE_WRITE_COIL = "write_coil"
SERVICE_WRITE_REGISTER = "write_register"
DEFAULT_SCAN_INTERVAL = 15  # seconds

# binary_sensor.py
CONF_INPUTS = "inputs"
CONF_INPUT_TYPE = "input_type"

# sensor.py
# CONF_DATA_TYPE = "data_type"
DEFAULT_STRUCT_FORMAT = {
    DATA_TYPE_INT: {1: "h", 2: "i", 4: "q"},
    DATA_TYPE_UINT: {1: "H", 2: "I", 4: "Q"},
    DATA_TYPE_FLOAT: {1: "e", 2: "f", 4: "d"},
}

# switch.py
CONF_STATE_OFF = "state_off"
CONF_STATE_ON = "state_on"
CONF_VERIFY_REGISTER = "verify_register"
CONF_VERIFY_STATE = "verify_state"

# climate.py
CONF_CLIMATES = "climates"
CONF_TARGET_TEMP = "target_temp_register"
CONF_CURRENT_TEMP = "current_temp_register"
CONF_CURRENT_TEMP_REGISTER_TYPE = "current_temp_register_type"
CONF_DATA_TYPE = "data_type"
CONF_DATA_COUNT = "data_count"
CONF_UNIT = "temperature_unit"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_STEP = "temp_step"
DEFAULT_STRUCTURE_PREFIX = ">f"
DEFAULT_TEMP_UNIT = "C"

# cover.py
CONF_STATE_OPEN = "state_open"
CONF_STATE_CLOSED = "state_closed"
CONF_STATE_OPENING = "state_opening"
CONF_STATE_CLOSING = "state_closing"
CONF_STATUS_REGISTER = "status_register"
CONF_STATUS_REGISTER_TYPE = "status_register_type"
DEFAULT_SLAVE = 1
