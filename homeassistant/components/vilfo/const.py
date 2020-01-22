"""Constants for the Vilfo Router integration."""
ATTR_DEFAULT_HOST = "admin.vilfo.com"
ATTR_ICON = "icon"
ATTR_GENERIC = "generic"
ATTR_LABEL = "label"
ATTR_LOAD = "load"
ATTR_ROUTER_NAME = "Vilfo Router"
ATTR_ROUTER_MANUFACTURER = "Vilfo AB"
ATTR_ROUTER_MODEL = "Vilfo Router"
ATTR_UNIT = "unit"
ATTR_UPTIME = "uptime"

DOMAIN = "vilfo"

UNIT_MINUTES = "m"
UNIT_PERCENT = "%"


SENSOR_TYPES = {
    "generic": {ATTR_LABEL: ATTR_GENERIC.title(), ATTR_UNIT: None, ATTR_ICON: None},
    "load": {
        ATTR_LABEL: ATTR_LOAD.title(),
        ATTR_UNIT: UNIT_PERCENT,
        ATTR_ICON: "mdi:memory",
    },
    "uptime": {
        ATTR_LABEL: ATTR_UPTIME.title(),
        ATTR_UNIT: UNIT_MINUTES,
        ATTR_ICON: "mdi:timer",
    },
}
