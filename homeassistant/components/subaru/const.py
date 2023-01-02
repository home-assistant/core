"""Constants for the Subaru integration."""
from subarulink.const import ALL_DOORS, DRIVERS_DOOR, TAILGATE_DOOR

from homeassistant.const import Platform

DOMAIN = "subaru"
FETCH_INTERVAL = 300
UPDATE_INTERVAL = 7200
CONF_UPDATE_ENABLED = "update_enabled"
CONF_COUNTRY = "country"

# entry fields
ENTRY_CONTROLLER = "controller"
ENTRY_COORDINATOR = "coordinator"
ENTRY_VEHICLES = "vehicles"

# update coordinator name
COORDINATOR_NAME = "subaru_data"

# info fields
VEHICLE_VIN = "vin"
VEHICLE_MODEL_NAME = "model_name"
VEHICLE_MODEL_YEAR = "model_year"
VEHICLE_NAME = "display_name"
VEHICLE_HAS_EV = "is_ev"
VEHICLE_API_GEN = "api_gen"
VEHICLE_HAS_REMOTE_START = "has_res"
VEHICLE_HAS_REMOTE_SERVICE = "has_remote"
VEHICLE_HAS_SAFETY_SERVICE = "has_safety"
VEHICLE_LAST_UPDATE = "last_update"
VEHICLE_STATUS = "status"


API_GEN_1 = "g1"
API_GEN_2 = "g2"
MANUFACTURER = "Subaru"

PLATFORMS = [
    Platform.LOCK,
    Platform.SENSOR,
]

SERVICE_LOCK = "lock"
SERVICE_UNLOCK = "unlock"
SERVICE_UNLOCK_SPECIFIC_DOOR = "unlock_specific_door"

ATTR_DOOR = "door"

UNLOCK_DOOR_ALL = "all"
UNLOCK_DOOR_DRIVERS = "driver"
UNLOCK_DOOR_TAILGATE = "tailgate"
UNLOCK_VALID_DOORS = {
    UNLOCK_DOOR_ALL: ALL_DOORS,
    UNLOCK_DOOR_DRIVERS: DRIVERS_DOOR,
    UNLOCK_DOOR_TAILGATE: TAILGATE_DOOR,
}

ICONS = {
    "Avg Fuel Consumption": "mdi:leaf",
    "EV Range": "mdi:ev-station",
    "Odometer": "mdi:road-variant",
    "Range": "mdi:gas-station",
}
