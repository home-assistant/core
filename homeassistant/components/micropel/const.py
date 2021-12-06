"""Constants for the Micropel integration."""
from enum import Enum

DOMAIN = "micropel"

"""Constants used in micropel integration."""


class SupportedPlatforms(Enum):
    """Supported platforms."""

    SENSOR = "sensor"


# Default conf values
DEFAULT_PLC = 0

# configuration names
CONF_CONNECTION_TCP = "tcp"
CONF_PLC = "plc"
CONF_COMMUNICATOR_TYPE = "type"
CONF_REGISTER_TYPE = "register_type"
CONF_SCALE = "scale"
CONF_PRECISION = "precision"
CONF_DATA_TYPE = "data_type"

# communicator types
COMMUNICATOR_TYPE_MPC300 = "MPC300"
COMMUNICATOR_TYPE_MPC400 = "MPC400"

# data types
DATA_TYPE_FLOAT = "float"
DATA_TYPE_INT = "int"

# call types
REGISTER_TYPE_WORD = "word"
REGISTER_TYPE_LONG_WORD = "long_word"
