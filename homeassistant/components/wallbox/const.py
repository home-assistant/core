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
CONF_ADDED_ENERGY_KEY = "added_energy"
CONF_ADDED_RANGE_KEY = "added_range"
CONF_CHARGING_POWER_KEY = "charging_power"
CONF_CHARGING_SPEED_KEY = "charging_speed"
CONF_CHARGING_TIME_KEY = "charging_time"
CONF_COST_KEY = "cost"
CONF_CURRENT_MODE_KEY = "current_mode"
CONF_DATA_KEY = "config_data"
CONF_DEPOT_PRICE_KEY = "depot_price"
CONF_MAX_AVAILABLE_POWER_KEY = "max_available_power"
CONF_MAX_CHARGING_CURRENT_KEY = "max_charging_current"
CONF_STATE_OF_CHARGE_KEY = "state_of_charge"
CONF_STATUS_DESCRIPTION_KEY = "status_description"

CONF_CONNECTIONS = "connections"
CONF_ROUND = "round"

CONF_SENSOR_TYPES = {
    CONF_CHARGING_POWER_KEY: {
        CONF_ICON: None,
        CONF_NAME: "Charging Power",
        CONF_ROUND: 2,
        CONF_UNIT_OF_MEASUREMENT: POWER_KILO_WATT,
        CONF_DEVICE_CLASS: DEVICE_CLASS_POWER,
    },
    CONF_MAX_AVAILABLE_POWER_KEY: {
        CONF_ICON: None,
        CONF_NAME: "Max Available Power",
        CONF_ROUND: 0,
        CONF_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
        CONF_DEVICE_CLASS: DEVICE_CLASS_CURRENT,
    },
    CONF_CHARGING_SPEED_KEY: {
        CONF_ICON: "mdi:speedometer",
        CONF_NAME: "Charging Speed",
        CONF_ROUND: 0,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_DEVICE_CLASS: None,
    },
    CONF_ADDED_RANGE_KEY: {
        CONF_ICON: "mdi:map-marker-distance",
        CONF_NAME: "Added Range",
        CONF_ROUND: 0,
        CONF_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
        CONF_DEVICE_CLASS: None,
    },
    CONF_ADDED_ENERGY_KEY: {
        CONF_ICON: None,
        CONF_NAME: "Added Energy",
        CONF_ROUND: 2,
        CONF_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        CONF_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
    },
    CONF_CHARGING_TIME_KEY: {
        CONF_ICON: "mdi:timer",
        CONF_NAME: "Charging Time",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_DEVICE_CLASS: None,
    },
    CONF_COST_KEY: {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Cost",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_DEVICE_CLASS: None,
    },
    CONF_STATE_OF_CHARGE_KEY: {
        CONF_ICON: None,
        CONF_NAME: "State of Charge",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: PERCENTAGE,
        CONF_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
    },
    CONF_CURRENT_MODE_KEY: {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Current Mode",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_DEVICE_CLASS: None,
    },
    CONF_DEPOT_PRICE_KEY: {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Depot Price",
        CONF_ROUND: 2,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_DEVICE_CLASS: None,
    },
    CONF_STATUS_DESCRIPTION_KEY: {
        CONF_ICON: "mdi:ev-station",
        CONF_NAME: "Status Description",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_DEVICE_CLASS: None,
    },
    CONF_MAX_CHARGING_CURRENT_KEY: {
        CONF_ICON: None,
        CONF_NAME: "Max. Charging Current",
        CONF_ROUND: None,
        CONF_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
        CONF_DEVICE_CLASS: DEVICE_CLASS_CURRENT,
    },
}
