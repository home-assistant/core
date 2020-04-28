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
CONF_OFFSET = "offset"
CONF_COILS = "coils"

# integration names
DEFAULT_HUB = "default"
MODBUS_DOMAIN = "modbus"

# data types
DATA_TYPE_CUSTOM = "custom"
DATA_TYPE_FLOAT = "float"
DATA_TYPE_INT = "int"
DATA_TYPE_UINT = "uint"

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

# binary_sensor.py
CONF_INPUTS = "inputs"
CONF_INPUT_TYPE = "input_type"
CONF_ADDRESS = "address"

# sensor.py
# CONF_DATA_TYPE = "data_type"

# switch.py
CONF_STATE_OFF = "state_off"
CONF_STATE_ON = "state_on"
CONF_VERIFY_REGISTER = "verify_register"
CONF_VERIFY_STATE = "verify_state"

# climate.py
CONF_TARGET_TEMP = "target_temp_register"
CONF_CURRENT_TEMP = "current_temp_register"
CONF_CURRENT_TEMP_REGISTER_TYPE = "current_temp_register_type"
CONF_DATA_TYPE = "data_type"
CONF_DATA_COUNT = "data_count"
CONF_UNIT = "temperature_unit"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_STEP = "temp_step"
