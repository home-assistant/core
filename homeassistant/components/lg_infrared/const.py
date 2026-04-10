"""Constants for the LG IR integration."""

from enum import StrEnum

DOMAIN = "lg_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_DEVICE_TYPE = "device_type"

CONF_REGION = "region"
REGION_GLOBAL = "global"
REGION_JAPAN = "japan"

class LGDeviceType(StrEnum):
    """LG device types."""

    TV = "tv"
