"""Constants for volvooncall."""

from datetime import timedelta

DOMAIN = "volvooncall"

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=1)

CONF_SERVICE_URL = "service_url"
CONF_SCANDINAVIAN_MILES = "scandinavian_miles"
CONF_MUTABLE = "mutable"

UNIT_SYSTEM_SCANDINAVIAN_MILES = "scandinavian_miles"
UNIT_SYSTEM_METRIC = "metric"
UNIT_SYSTEM_IMPERIAL = "imperial"

PLATFORMS = {
    "sensor": "sensor",
    "binary_sensor": "binary_sensor",
    "lock": "lock",
    "device_tracker": "device_tracker",
    "switch": "switch",
}

RESOURCES = [
    "position",
    "lock",
    "heater",
    "odometer",
    "trip_meter1",
    "trip_meter2",
    "average_speed",
    "fuel_amount",
    "fuel_amount_level",
    "average_fuel_consumption",
    "distance_to_empty",
    "washer_fluid_level",
    "brake_fluid",
    "service_warning_status",
    "bulb_failures",
    "battery_range",
    "battery_level",
    "time_to_fully_charged",
    "battery_charge_status",
    "engine_start",
    "last_trip",
    "is_engine_running",
    "doors_hood_open",
    "doors_tailgate_open",
    "doors_front_left_door_open",
    "doors_front_right_door_open",
    "doors_rear_left_door_open",
    "doors_rear_right_door_open",
    "windows_front_left_window_open",
    "windows_front_right_window_open",
    "windows_rear_left_window_open",
    "windows_rear_right_window_open",
    "tyre_pressure_front_left_tyre_pressure",
    "tyre_pressure_front_right_tyre_pressure",
    "tyre_pressure_rear_left_tyre_pressure",
    "tyre_pressure_rear_right_tyre_pressure",
    "any_door_open",
    "any_window_open",
]

VOLVO_DISCOVERY_NEW = "volvo_discovery_new"
