"""Constants for the LG IR integration."""

from enum import StrEnum

DOMAIN = "lg_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_INFRARED_RECEIVER_ENTITY_ID = "infrared_receiver_entity_id"
CONF_DEVICE_TYPE = "device_type"
CONF_HVAC_MODES = "hvac_modes"

MIN_TEMP = 16
MAX_TEMP = 30

FAN_QUIET = "quiet"


class LGDeviceType(StrEnum):
    """LG device types."""

    TV = "tv"
    AC = "ac"
