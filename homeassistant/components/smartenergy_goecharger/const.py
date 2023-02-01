"""Constants re-used across different files."""

from enum import Enum

API = "api"
CHARGERS_API = "chargers_api"
CONF_CHARGERS = "chargers"
DOMAIN = "smartenergy_goecharger"
INIT_STATE = "init"
MANUFACTURER = "go-e GmbH"
UNSUB_OPTIONS_UPDATE_LISTENER = "unsub_options_update_listener"
STATUS = "status"
ONLINE = "online"
OFFLINE = "offline"

# API attributes

CAR_STATUS = "car_status"
CHARGER_ACCESS = "charger_access"
CHARGER_FORCE_CHARGING = "charger_force_charging"
CHARGER_MAX_CURRENT = "charger_max_current"
CHARGING_ALLOWED = "charging_allowed"
ENERGY_SINCE_CAR_CONNECTED = "energy_since_car_connected"
ENERGY_TOTAL = "energy_total"
MIN_CHARGING_CURRENT_LIMIT = "min_charging_current_limit"
MAX_CHARGING_CURRENT_LIMIT = "max_charging_current_limit"
PHASE_SWITCH_MODE = "phase_switch_mode"
PHASES_NUMBER_CONNECTED = "phases_number_connected"
TRANSACTION = "transaction"

# Custom attributes

WALLBOX_CONTROL = "wallbox_control"

# Car param status values


class CarStatus(str, Enum):
    """List of possible car status values."""

    # 1
    CHARGER_READY_NO_CAR = "Charger ready, no car connected"
    # 2
    CAR_CHARGING = "Car is charging"
    # 3
    CAR_CONNECTED_AUTH_REQUIRED = "Car connected, authentication required"
    # 4
    CHARGING_FINISHED_DISCONNECT = "Charging finished, car can be disconnected"
