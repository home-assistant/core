"""Const for Plugwise USB-stick."""

from homeassistant.components.switch import DEVICE_CLASS_OUTLET
from homeassistant.const import DEVICE_CLASS_POWER, ENERGY_KILO_WATT_HOUR, POWER_WATT

DOMAIN = "plugwise_stick"
CONF_USB_PATH = "usb_path"

# Sensor IDs
AVAILABLE_SENSOR_ID = "available"
CURRENT_POWER_SENSOR_ID = "power_1s"
TODAY_ENERGY_SENSOR_ID = "power_con_today"

# Sensor types
SENSORS = {
    AVAILABLE_SENSOR_ID: {
        "class": None,
        "enabled_default": False,
        "icon": "mdi:signal-off",
        "name": "Available",
        "state": "get_available",
        "unit": None,
    },
    CURRENT_POWER_SENSOR_ID: {
        "class": DEVICE_CLASS_POWER,
        "enabled_default": True,
        "icon": None,
        "name": "Power usage",
        "state": "get_power_usage",
        "unit": POWER_WATT,
    },
    TODAY_ENERGY_SENSOR_ID: {
        "class": DEVICE_CLASS_POWER,
        "enabled_default": True,
        "icon": None,
        "name": "Power consumption today",
        "state": "get_power_consumption_today",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
}

# Switch types
SWITCHES = {
    "relay": {
        "class": DEVICE_CLASS_OUTLET,
        "enabled_default": True,
        "icon": None,
        "name": "Relay state",
        "state": "get_relay_state",
        "switch": "set_relay_state",
        "unit": "state",
    }
}
