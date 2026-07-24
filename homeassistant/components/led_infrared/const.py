"""Constants for the LED Infrared integration."""

from enum import StrEnum

DOMAIN = "led_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_DEVICE_TYPE = "device_type"


class LEDIrDeviceType(StrEnum):
    """LED Infrared device types."""

    GENERIC_13_KEY = "generic_13_key"
    GENERIC_24_KEY = "generic_24_key"
    GENERIC_40_KEY = "generic_40_key"
    GENERIC_44_KEY = "generic_44_key"
