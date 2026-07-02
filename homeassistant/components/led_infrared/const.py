"""Constants for the LED Infrared integration."""

from enum import StrEnum

DOMAIN = "led_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_INFRARED_RECEIVER_ENTITY_ID = "infrared_receiver_entity_id"
CONF_DEVICE_TYPE = "device_type"


class LEDIrDeviceType(StrEnum):
    """LED Infrared device types."""

    GENERIC_24_KEY = "generic_24_key"
    GENERIC_13_KEY = "generic_13_key"


SUPPORTED_EFFECTS = {
    LEDIrDeviceType.GENERIC_24_KEY: ["flash", "strobe", "fade", "smooth"],
    LEDIrDeviceType.GENERIC_13_KEY: [
        "mode_1",
        "mode_2",
        "mode_3",
        "mode_4",
        "mode_5",
        "mode_6",
        "mode_7",
        "mode_8",
    ],
}


SUPPORTED_COLORS = {
    LEDIrDeviceType.GENERIC_24_KEY: [
        "red",
        "green",
        "blue",
        "white",
        "tomato",
        "light_green",
        "sky_blue",
        "orange_red",
        "cyan",
        "rebecca_purple",
        "orange",
        "turquoise",
        "purple",
        "yellow",
        "dark_cyan",
        "plum",
    ],
}
