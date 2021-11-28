"""Constants for the Micropel integration."""

DOMAIN = "micropel"

"""Constants used in micropel integration."""

# configuration names
CONF_HUB = "hub"
CONF_PLC = "plc"
CONF_COMMUNICATOR_TYPE = "type"
CONF_BIT_INDEX = "bit_index"
CONF_REGISTER_TYPE = "register_type"
CONF_SCALE = "scale"
CONF_PRECISION = "precision"

# integration names
DEFAULT_HUB = "micropel_hub"

# communicator types
COMMUNICATOR_TYPE_MPC300 = "MPC300"
COMMUNICATOR_TYPE_MPC400 = "MPC400"

# data types
DATA_TYPE_FLOAT = "float"
DATA_TYPE_INT = "int"

# call types
REGISTER_TYPE_BIT = "bit"
REGISTER_TYPE_WORD = "word"
REGISTER_TYPE_LONG_WORD = "long_word"

# the following constants are TBD.
# changing those in general causes a breaking change, because
# the contents of configuration.yaml needs to be updated,
# therefore they are left to a later date.
# but kept here, with a reference to the file using them.

# __init.py
ATTR_VALUE = "value"
SERVICE_WRITE_COIL = "write_coil"
SERVICE_WRITE_REGISTER = "write_register"
DEFAULT_SCAN_INTERVAL = 15  # seconds

# binary_sensor.py
CONF_INPUTS = "inputs"
CONF_INPUT_TYPE = "input_type"

# switch.py
CONF_STATE_OFF = "state_off"
CONF_STATE_ON = "state_on"
CONF_VERIFY_REGISTER = "verify_register"
CONF_VERIFY_STATE = "verify_state"

# climate.py
CONF_CLIMATES = "climates"
CONF_CLIMATE = "climate"
CONF_TARGET_TEMP_ADDRESS = "target_temp_address"
CONF_CURRENT_TEMP_ADDRESS = "current_temp_address"
CONF_DATA_TYPE = "data_type"
CONF_DATA_COUNT = "data_count"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_STEP = "temp_step"
DEFAULT_STRUCTURE_PREFIX = ">f"
DEFAULT_TEMP_UNIT = "C"

# cover.py
CONF_COVER = "cover"
CONF_STATE_OPEN = "state_open"
CONF_STATE_CLOSED = "state_closed"
CONF_STATE_OPENING = "state_opening"
CONF_STATE_CLOSING = "state_closing"
CONF_STATUS_REGISTER = "status_register"
CONF_STATUS_REGISTER_TYPE = "status_register_type"
DEFAULT_PLC = 0
