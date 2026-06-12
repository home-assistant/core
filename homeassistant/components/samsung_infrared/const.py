"""Constants for the Samsung IR integration."""

from enum import StrEnum

DOMAIN = "samsung_infrared"
CONF_INFRARED_EMITTER_ENTITY_ID = "infrared_emitter_entity_id"
CONF_DEVICE_TYPE = "device_type"


class SamsungDeviceType(StrEnum):
    """Samsung device types."""

    TV = "tv"
    AC_2A20 = "samsung_ac_2a20"
    AC_0292 = "samsung_ac_0292"
