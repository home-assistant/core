"""Const for Plugwise USB-stick."""

from homeassistant.const import (
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    TIME_MILLISECONDS,
)

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
    "ping": {
        "class": None,
        "enabled_default": False,
        "icon": "mdi:speedometer",
        "name": "Ping roundtrip",
        "state": "get_ping",
        "unit": TIME_MILLISECONDS,
    },
    CURRENT_POWER_SENSOR_ID: {
        "class": DEVICE_CLASS_POWER,
        "enabled_default": True,
        "icon": "mdi:flash",
        "name": "Power usage",
        "state": "get_power_usage",
        "unit": POWER_WATT,
    },
    "power_8s": {
        "class": DEVICE_CLASS_POWER,
        "enabled_default": False,
        "icon": "mdi:flash",
        "name": "Power usage 8 seconds",
        "state": "get_power_usage_8_sec",
        "unit": POWER_WATT,
    },
    "power_con_cur_hour": {
        "class": DEVICE_CLASS_POWER,
        "enabled_default": True,
        "icon": "mdi:flash",
        "name": "Power consumption current hour",
        "state": "get_power_consumption_current_hour",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "power_con_prev_hour": {
        "class": DEVICE_CLASS_POWER,
        "enabled_default": True,
        "icon": "mdi:flash",
        "name": "Power consumption previous hour",
        "state": "get_power_consumption_prev_hour",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    TODAY_ENERGY_SENSOR_ID: {
        "class": DEVICE_CLASS_POWER,
        "enabled_default": True,
        "icon": "mdi:flash",
        "name": "Power consumption today",
        "state": "get_power_consumption_today",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "power_con_yesterday": {
        "class": DEVICE_CLASS_POWER,
        "enabled_default": True,
        "icon": "mdi:flash",
        "name": "Power consumption yesterday",
        "state": "get_power_consumption_yesterday",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "power_prod_cur_hour": {
        "class": DEVICE_CLASS_POWER,
        "enabled_default": False,
        "icon": "mdi:flash",
        "name": "Power production current hour",
        "state": "get_power_production_current_hour",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
    "power_prod_prev_hour": {
        "class": DEVICE_CLASS_POWER,
        "enabled_default": False,
        "icon": "mdi:flash",
        "name": "Power production previous hour",
        "state": "get_power_production_previous_hour",
        "unit": ENERGY_KILO_WATT_HOUR,
    },
}

# Switch types
SWITCHES = {
    "relay": {
        "class": DEVICE_CLASS_POWER,
        "enabled_default": True,
        "icon": "mdi:power-socket-eu",
        "name": "Relay state",
        "state": "get_relay_state",
        "switch": "set_relay_state",
        "unit": "state",
    }
}
