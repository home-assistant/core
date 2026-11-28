"""Constants for the APsystems Local API integration."""

from logging import Logger, getLogger
from typing import Final

LOGGER: Logger = getLogger(__package__)
DOMAIN = "apsystems"
DEFAULT_PORT = 8050

# One domain covers two device generations, told apart by device_type in the
# entry data. An entry without that key predates Lake support and stays on the
# EZ1 path.
CONF_DEVICE_TYPE: Final = "device_type"
DEVICE_TYPE_EZ1: Final = "ez1"
DEVICE_TYPE_LAKE6: Final = "lake6"
