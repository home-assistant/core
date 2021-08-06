"""Constants for the Wallbox integration."""
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ELECTRIC_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    POWER_KILO_WATT,
)

DOMAIN = "wallbox"

CONF_STATION = "station"

CONF_CONNECTIONS = "connections"
CONF_ROUND = "round"

CONF_SENSOR_TYPES = {
    "charging_power": {
        CONF_ICON: None,
        CONF_NAME: "Charging Power",
        CONF_ROUND: 2,
        CONF_UNIT_OF_MEASUREMENT: POWER_KILO_WATT,
        CONF_DEVICE_CLASS: DEVICE_CLASS_POWER,
    },
    "max_available_power": {
        CONF_ICON: None,
        CONF_NAME: "Max Available Power",
        CONF_ROUND: 0,
        CONF_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
        CONF_DEVICE_CLASS: DEVICE_CLASS_CURRENT,
    },
    "charging_speed": {
        CONF_ICON: "mdi:speedometer",
        CONF_NAME: "Charging Speed",
        CONF_ROUND: 0,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_DEVICE_CLASS: None,
    },
    "added_range": {
        CONF_ICON: "mdi:map-marker-distance",
        CONF_NAME: "Added Range",
        CONF_ROUND: 0,
        CONF_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
        CONF_DEVICE_CLASS: None,
    },
    "added_energy": {
        CONF_ICON: None,
        CONF_NAME: "Added Energy",
        CONF_ROUND: 2,
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
    },
    "charging_time": {
        CONF_ICON: "mdi:timer",
        CONF_NAME: "Charging Time",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_DEVICE_CLASS: None,
    },
    "cost": {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Cost",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_DEVICE_CLASS: None,
    },
    "state_of_charge": {
        CONF_ICON: None,
        CONF_NAME: "State of Charge",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: PERCENTAGE,
        CONF_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
    },
    "current_mode": {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Current Mode",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_DEVICE_CLASS: None,
    },
    "depot_price": {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Depot Price",
        CONF_ROUND: 2,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_DEVICE_CLASS: None,
    },
    "status_description": {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Status Description",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_DEVICE_CLASS: None,
    },
    "max_charging_current": {
        CONF_ICON: None,
        CONF_NAME: "Max. Charging Current",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
        CONF_DEVICE_CLASS: DEVICE_CLASS_CURRENT,
    },
}
