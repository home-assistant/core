"""Constants for the Wallbox integration."""
from homeassistant.const import (
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    POWER_KILO_WATT,
)

DOMAIN = "wallbox"

CONF_STATION = "station"

CONF_CONNECTIONS = "connections"

SENSOR_TYPES = {
    "charging_power": {
        "ATTR_ICON": "mdi:ev-station",
        "ATTR_LABEL": "Charging Power",
        "ATTR_ROUND": 2,
        "ATTR_UNIT": POWER_KILO_WATT,
        "ATTR_ENABLED": True,
    },
    "max_available_power": {
        "ATTR_ICON": "mdi:ev-station",
        "ATTR_LABEL": "Max Available Power",
        "ATTR_ROUND": 0,
        "ATTR_UNIT": ELECTRICAL_CURRENT_AMPERE,
        "ATTR_ENABLED": True,
    },
    "charging_speed": {
        "ATTR_ICON": "mdi:speedometer",
        "ATTR_LABEL": "Charging Speed",
        "ATTR_ROUND": 0,
        "ATTR_UNIT": None,
        "ATTR_ENABLED": True,
    },
    "added_range": {
        "ATTR_ICON": "mdi:map-marker-distance",
        "ATTR_LABEL": "Added Range",
        "ATTR_ROUND": 0,
        "ATTR_UNIT": LENGTH_KILOMETERS,
        "ATTR_ENABLED": True,
    },
    "added_energy": {
        "ATTR_ICON": "mdi:battery-positive",
        "ATTR_LABEL": "Added Energy",
        "ATTR_ROUND": 2,
        "ATTR_UNIT": ENERGY_KILO_WATT_HOUR,
        "ATTR_ENABLED": True,
    },
    "charging_time": {
        "ATTR_ICON": "mdi:timer",
        "ATTR_LABEL": "Charging Time",
        "ATTR_ROUND": None,
        "ATTR_UNIT": None,
        "ATTR_ENABLED": True,
    },
    "cost": {
        "ATTR_ICON": "mdi:ev-station",
        "ATTR_LABEL": "Cost",
        "ATTR_ROUND": None,
        "ATTR_UNIT": None,
        "ATTR_ENABLED": True,
    },
    "state_of_charge": {
        "ATTR_ICON": "mdi:battery-charging-80",
        "ATTR_LABEL": "State of Charge",
        "ATTR_ROUND": None,
        "ATTR_UNIT": PERCENTAGE,
        "ATTR_ENABLED": True,
    },
    "current_mode": {
        "ATTR_ICON": "mdi:ev-station",
        "ATTR_LABEL": "Current Mode",
        "ATTR_ROUND": None,
        "ATTR_UNIT": None,
        "ATTR_ENABLED": True,
    },
    "depot_price": {
        "ATTR_ICON": "mdi:ev-station",
        "ATTR_LABEL": "Depot Price",
        "ATTR_ROUND": 2,
        "ATTR_UNIT": None,
        "ATTR_ENABLED": True,
    },
    "status_description": {
        "ATTR_ICON": "mdi:ev-station",
        "ATTR_LABEL": "Status Description",
        "ATTR_ROUND": None,
        "ATTR_UNIT": None,
        "ATTR_ENABLED": True,
    },
}
