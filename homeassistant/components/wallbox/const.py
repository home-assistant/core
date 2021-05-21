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
        "ST_ICON": "mdi:ev-station",
        "ST_LABEL": "Charging Power",
        "ST_ROUND": 2,
        "ST_UNIT": POWER_KILO_WATT,
        "ST_ENABLED": True,
    },
    "max_available_power": {
        "ST_ICON": "mdi:ev-station",
        "ST_LABEL": "Max Available Power",
        "ST_ROUND": 0,
        "ST_UNIT": ELECTRICAL_CURRENT_AMPERE,
        "ST_ENABLED": True,
    },
    "charging_speed": {
        "ST_ICON": "mdi:speedometer",
        "ST_LABEL": "Charging Speed",
        "ST_ROUND": 0,
        "ST_UNIT": None,
        "ST_ENABLED": True,
    },
    "added_range": {
        "ST_ICON": "mdi:map-marker-distance",
        "ST_LABEL": "Added Range",
        "ST_ROUND": 0,
        "ST_UNIT": LENGTH_KILOMETERS,
        "ST_ENABLED": True,
    },
    "added_energy": {
        "ST_ICON": "mdi:battery-positive",
        "ST_LABEL": "Added Energy",
        "ST_ROUND": 2,
        "ST_UNIT": ENERGY_KILO_WATT_HOUR,
        "ST_ENABLED": True,
    },
    "charging_time": {
        "ST_ICON": "mdi:timer",
        "ST_LABEL": "Charging Time",
        "ST_ROUND": None,
        "ST_UNIT": None,
        "ST_ENABLED": True,
    },
    "cost": {
        "ST_ICON": "mdi:ev-station",
        "ST_LABEL": "Cost",
        "ST_ROUND": None,
        "ST_UNIT": None,
        "ST_ENABLED": True,
    },
    "state_of_charge": {
        "ST_ICON": "mdi:battery-charging-80",
        "ST_LABEL": "State of Charge",
        "ST_ROUND": None,
        "ST_UNIT": PERCENTAGE,
        "ST_ENABLED": True,
    },
    "current_mode": {
        "ST_ICON": "mdi:ev-station",
        "ST_LABEL": "Current Mode",
        "ST_ROUND": None,
        "ST_UNIT": None,
        "ST_ENABLED": True,
    },
    "depot_price": {
        "ST_ICON": "mdi:ev-station",
        "ST_LABEL": "Depot Price",
        "ST_ROUND": 2,
        "ST_UNIT": None,
        "ST_ENABLED": True,
    },
    "status_description": {
        "ST_ICON": "mdi:ev-station",
        "ST_LABEL": "Status Description",
        "ST_ROUND": None,
        "ST_UNIT": None,
        "ST_ENABLED": True,
    },
}
