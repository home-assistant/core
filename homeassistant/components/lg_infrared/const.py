"""Constants for the LG IR integration."""

from enum import StrEnum

DOMAIN = "lg_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_DEVICE_TYPE = "device_type"


class LGDeviceType(StrEnum):
    """LG device types."""

    TV = "tv"
