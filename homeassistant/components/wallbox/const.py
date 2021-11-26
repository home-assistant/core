"""Constants for the Wallbox integration."""
from typing import Literal

DOMAIN = "wallbox"

CONF_STATION = "station"
CONF_CONNECTIONS = "connections"

CONF_ADDED_ENERGY_KEY: Literal["added_energy"] = "added_energy"
CONF_ADDED_RANGE_KEY: Literal["added_range"] = "added_range"
CONF_CHARGING_POWER_KEY: Literal["charging_power"] = "charging_power"
CONF_CHARGING_SPEED_KEY: Literal["charging_speed"] = "charging_speed"
CONF_CHARGING_TIME_KEY: Literal["charging_time"] = "charging_time"
CONF_COST_KEY: Literal["cost"] = "cost"
CONF_CURRENT_MODE_KEY: Literal["current_mode"] = "current_mode"
CONF_DATA_KEY: Literal["config_data"] = "config_data"
CONF_DEPOT_PRICE_KEY: Literal["depot_price"] = "depot_price"
CONF_MAX_AVAILABLE_POWER_KEY: Literal["max_available_power"] = "max_available_power"
CONF_MAX_CHARGING_CURRENT_KEY: Literal["max_charging_current"] = "max_charging_current"
CONF_STATE_OF_CHARGE_KEY: Literal["state_of_charge"] = "state_of_charge"
CONF_STATUS_DESCRIPTION_KEY: Literal["status_description"] = "status_description"
