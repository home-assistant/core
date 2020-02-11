"""Constants for the Vilfo Router integration."""
from homeassistant.const import DEVICE_CLASS_TIMESTAMP

DOMAIN = "vilfo"

ATTR_API_DATA_FIELD = "api_data_field"
ATTR_API_DATA_FIELD_LOAD = "load"
ATTR_API_DATA_FIELD_BOOT_TIME = "boot_time"
ATTR_DEVICE_CLASS = "device_class"
ATTR_ICON = "icon"
ATTR_LABEL = "label"
ATTR_LOAD = "load"
ATTR_UNIT = "unit"
ATTR_BOOT_TIME = "boot_time"

ROUTER_DEFAULT_HOST = "admin.vilfo.com"
ROUTER_DEFAULT_MODEL = "Vilfo Router"
ROUTER_DEFAULT_NAME = "Vilfo Router"
ROUTER_MANUFACTURER = "Vilfo AB"

UNIT_PERCENT = "%"

SENSOR_TYPES = {
    "load": {
        ATTR_LABEL: ATTR_LOAD.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENT,
        ATTR_ICON: "mdi:memory",
        ATTR_API_DATA_FIELD: ATTR_API_DATA_FIELD_LOAD,
    },
    "boot_time": {
        ATTR_LABEL: ATTR_BOOT_TIME.replace("_", " ").title(),
        ATTR_ICON: "mdi:timer",
        ATTR_API_DATA_FIELD: ATTR_API_DATA_FIELD_BOOT_TIME,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
    },
}
