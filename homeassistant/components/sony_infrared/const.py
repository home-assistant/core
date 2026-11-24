"""Constants for the Sony Infrared integration."""

from enum import StrEnum

DOMAIN = "sony_infrared"
CONF_DEVICE_TYPE = "device_type"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"


class SonyDeviceType(StrEnum):
    """Sony device types."""

    TV = "tv"
