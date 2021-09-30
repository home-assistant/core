"""Define constants for the OpenUV component."""
import logging

DOMAIN = "openuv"
LOGGER = logging.getLogger(__package__)

CONF_FROM_WINDOW = "from_window"
CONF_TO_WINDOW = "to_window"

DATA_CLIENT = "data_client"
DATA_LISTENER = "data_listener"
DATA_PROTECTION_WINDOW = "protection_window"
DATA_UV = "uv"

DEFAULT_FROM_WINDOW = 3.5
DEFAULT_TO_WINDOW = 3.5

TYPE_CURRENT_OZONE_LEVEL = "current_ozone_level"
TYPE_CURRENT_UV_INDEX = "current_uv_index"
TYPE_CURRENT_UV_LEVEL = "current_uv_level"
TYPE_MAX_UV_INDEX = "max_uv_index"
TYPE_PROTECTION_WINDOW = "uv_protection_window"
TYPE_SAFE_EXPOSURE_TIME_1 = "safe_exposure_time_type_1"
TYPE_SAFE_EXPOSURE_TIME_2 = "safe_exposure_time_type_2"
TYPE_SAFE_EXPOSURE_TIME_3 = "safe_exposure_time_type_3"
TYPE_SAFE_EXPOSURE_TIME_4 = "safe_exposure_time_type_4"
TYPE_SAFE_EXPOSURE_TIME_5 = "safe_exposure_time_type_5"
TYPE_SAFE_EXPOSURE_TIME_6 = "safe_exposure_time_type_6"
