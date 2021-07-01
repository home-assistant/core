"""Constants for the Wallbox integration."""
from homeassistant.const import (
    CONF_ICON,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    POWER_KILO_WATT,
    STATE_UNAVAILABLE,
)

DOMAIN = "wallbox"

CONF_STATION = "station"

CONF_CONNECTIONS = "connections"
CONF_ROUND = "round"

CONF_SENSOR_TYPES = {
    "charging_power": {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Charging Power",
        CONF_ROUND: 2,
        CONF_UNIT_OF_MEASUREMENT: POWER_KILO_WATT,
        STATE_UNAVAILABLE: False,
    },
    "max_available_power": {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Max Available Power",
        CONF_ROUND: 0,
        CONF_UNIT_OF_MEASUREMENT: ELECTRICAL_CURRENT_AMPERE,
        STATE_UNAVAILABLE: False,
    },
    "charging_speed": {
        CONF_ICON: "mdi:speedometer",
        CONF_NAME: "Charging Speed",
        CONF_ROUND: 0,
        CONF_UNIT_OF_MEASUREMENT: None,
        STATE_UNAVAILABLE: False,
    },
    "added_range": {
        CONF_ICON: "mdi:map-marker-distance",
        CONF_NAME: "Added Range",
        CONF_ROUND: 0,
        CONF_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
        STATE_UNAVAILABLE: False,
    },
    "added_energy": {
        CONF_ICON: "mdi:battery-positive",
        CONF_NAME: "Added Energy",
        CONF_ROUND: 2,
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        STATE_UNAVAILABLE: False,
    },
    "charging_time": {
        CONF_ICON: "mdi:timer",
        CONF_NAME: "Charging Time",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        STATE_UNAVAILABLE: False,
    },
    "cost": {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Cost",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        STATE_UNAVAILABLE: False,
    },
    "state_of_charge": {
        CONF_ICON: "mdi:battery-charging-80",
        CONF_NAME: "State of Charge",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: PERCENTAGE,
        STATE_UNAVAILABLE: False,
    },
    "current_mode": {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Current Mode",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        STATE_UNAVAILABLE: False,
    },
    "depot_price": {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Depot Price",
        CONF_ROUND: 2,
        CONF_UNIT_OF_MEASUREMENT: None,
        STATE_UNAVAILABLE: False,
    },
    "status_description": {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Status Description",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        STATE_UNAVAILABLE: False,
    },
}
