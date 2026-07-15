"""Constants for the LG IR integration."""

from enum import StrEnum

DOMAIN = "lg_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_INFRARED_RECEIVER_ENTITY_ID = "infrared_receiver_entity_id"
CONF_DEVICE_TYPE = "device_type"
CONF_HVAC_MODES = "hvac_modes"

FAN_QUIET = "quiet"
FAN_MEDIUM_LOW = "medium_low"
FAN_MEDIUM_HIGH = "medium_high"


class LGDeviceType(StrEnum):
    """LG device types."""

    TV = "tv"
    AC = "ac"
