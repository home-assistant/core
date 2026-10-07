"""Constants for the Dyson Infrared integration."""

from enum import StrEnum

DOMAIN = "dyson_infrared"
CONF_INFRARED_EMITTER_ENTITY_ID = "infrared_emitter_entity_id"
CONF_DEVICE_TYPE = "device_type"


class DysonDeviceType(StrEnum):
    """Supported Dyson device types."""

    FAN = "fan"
