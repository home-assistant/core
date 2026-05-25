"""Constants for the Samsung IR integration."""

from enum import StrEnum

DOMAIN = "samsung_infrared"
CONF_INFRARED_EMITTER_ENTITY_ID = "infrared_emitter_entity_id"
CONF_DEVICE_TYPE = "device_type"


class SamsungDeviceType(StrEnum):
    """Samsung device types."""

    TV = "tv"
