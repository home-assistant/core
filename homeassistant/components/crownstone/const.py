"""Constants for the crownstone integration."""

DOMAIN = "crownstone"
CONF_SPHERE = "sphere"

CROWNSTONE_TYPES = {
    "PLUG": "Crownstone plug",
    "CROWNSTONE_USB": "Crownstone USB",
    "BUILTIN": "Crownstone built-in",
    "BUILTIN_ONE": "Crownstone built-in one",
    "GUIDESTONE": "Crownstone guidestone",
}

CROWNSTONE_EXCLUDE = ["CROWNSTONE_USB", "GUIDESTONE"]

PRESENCE_SPHERE = {"icon": "mdi:earth", "description": "Sphere presence"}

PRESENCE_LOCATION = {
    "icon": "mdi:map-marker-radius",
    "description": "Location presence",
}
