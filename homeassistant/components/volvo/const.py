"""Constants for the Volvo integration."""

from homeassistant.const import Platform

DOMAIN = "volvo"
PLATFORMS: list[Platform] = [Platform.SENSOR]

ATTR_API_TIMESTAMP = "api_timestamp"

CONF_VIN = "vin"

DATA_BATTERY_CAPACITY = "battery_capacity_kwh"

MANUFACTURER = "Volvo"

SCOPES = [
    "openid",
    "conve:battery_charge_level",
    "conve:brake_status",
    "conve:climatization_start_stop",
    "conve:command_accessibility",
    "conve:commands",
    "conve:diagnostics_engine_status",
    "conve:diagnostics_workshop",
    "conve:doors_status",
    "conve:engine_status",
    "conve:fuel_status",
    "conve:lock_status",
    "conve:odometer_status",
    "conve:trip_statistics",
    "conve:tyre_status",
    "conve:vehicle_relation",
    "conve:warnings",
    "conve:windows_status",
    "energy:battery_charge_level",
    "energy:charging_connection_status",
    "energy:charging_current_limit",
    "energy:charging_system_status",
    "energy:electric_range",
    "energy:estimated_charging_time",
    "energy:recharge_status",
    "energy:target_battery_level",
]
