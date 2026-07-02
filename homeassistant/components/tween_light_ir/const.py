"""Constants for the Tween Light Infrared integration."""

from enum import StrEnum

DOMAIN = "tween_light_ir"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_INFRARED_RECEIVER_ENTITY_ID = "infrared_receiver_entity_id"
CONF_DEVICE_TYPE = "device_type"


class TweenLightIrDeviceType(StrEnum):
    """Tween Light Infrared device types."""

    LED_STRIP = "led_strip"


DEVICE_TYPE_NAMES: dict[TweenLightIrDeviceType, str] = {
    TweenLightIrDeviceType.LED_STRIP: "LED Strip",
}
