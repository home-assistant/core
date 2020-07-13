"""Helper functions for the OpenRGB Integration."""
from openrgb.utils import DeviceType

from homeassistant.components.light import ENTITY_ID_FORMAT


def orgb_tuple(color):
    """Unpack the RGB Object provided by the client library."""
    return (color.red, color.green, color.blue)


def orgb_object_id(instance):
    """Return the ORGB Devices object id."""
    return f"{instance.name} {instance.device_id}".replace(" ", "_").lower()


def orgb_entity_id(instance):
    """Return the ORGB devices entity ID."""
    return ENTITY_ID_FORMAT.format(orgb_object_id(instance))


def orgb_icon(device_type):
    """Return a suitable icon for this device_type."""
    icons = {
        DeviceType.MOTHERBOARD: "view-dashboard-outline",
        DeviceType.DRAM: "memory",
        DeviceType.GPU: "expansion-card",
        DeviceType.COOLER: "fan",
        DeviceType.LEDSTRIP: "led-outline",
        DeviceType.KEYBOARD: "keyboard",
        DeviceType.MOUSE: "mouse",
        DeviceType.MOUSEMAT: "rug",
        DeviceType.HEADSET: "headset",
        DeviceType.HEADSET_STAND: "headset-dock",
        DeviceType.UNKNOWN: "crosshairs-question",
    }

    return icons.get(device_type, "lightbulb")
