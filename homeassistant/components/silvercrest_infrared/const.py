"""Constants for the SilverCrest Infrared integration."""

from enum import StrEnum

DOMAIN = "silvercrest_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_DEVICE_TYPE = "device_type"


class SilverCrestIrDeviceType(StrEnum):
    """SilverCrest Infrared device types."""

    FAN = "fan"
    MISTING_FAN = "misting_fan"
