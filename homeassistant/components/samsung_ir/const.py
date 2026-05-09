"""Constants for the Samsung IR integration."""

from enum import StrEnum

DOMAIN = "samsung_ir"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_DEVICE_TYPE = "device_type"


class SamsungDeviceType(StrEnum):
    """Samsung device types."""

    TV = "tv"
