"""Constants for the LED Infrared integration."""

from enum import StrEnum

DOMAIN = "led_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_DEVICE_TYPE = "device_type"


class LEDIrDeviceType(StrEnum):
    """LED Infrared device types."""

    GENERIC_24_KEY = "generic_24_key"
    GENERIC_13_KEY = "generic_13_key"
