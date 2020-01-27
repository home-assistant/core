"""Constants for the Vilfo Router integration."""
DOMAIN = "vilfo"

ATTR_API_DATA_FIELD = "api_data_field"
ATTR_API_DATA_FIELD_LOAD = "load"
ATTR_API_DATA_FIELD_UPTIME = "uptime_minutes"
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

UNIT_MINUTES = "m"
UNIT_PERCENT = "%"

SENSOR_TYPES = {
    "load": {
        ATTR_LABEL: ATTR_LOAD.title(),
        ATTR_UNIT: UNIT_PERCENT,
        ATTR_ICON: "mdi:memory",
        ATTR_API_DATA_FIELD: ATTR_API_DATA_FIELD_LOAD,
    },
    "uptime": {
        ATTR_LABEL: ATTR_UPTIME.title(),
        ATTR_UNIT: UNIT_MINUTES,
        ATTR_ICON: "mdi:timer",
        ATTR_API_DATA_FIELD: ATTR_API_DATA_FIELD_UPTIME,
    },
}
