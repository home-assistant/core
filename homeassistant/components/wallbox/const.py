"""Constants for the Wallbox integration."""

from enum import StrEnum

DOMAIN = "wallbox"
UPDATE_INTERVAL = 30

BIDIRECTIONAL_MODEL_PREFIXES = ["QS"]

CODE_KEY = "code"
CONF_STATION = "station"
CHARGER_ADDED_DISCHARGED_ENERGY_KEY = "added_discharged_energy"
CHARGER_ADDED_ENERGY_KEY = "added_energy"
CHARGER_ADDED_RANGE_KEY = "added_range"
CHARGER_CHARGING_POWER_KEY = "charging_power"
CHARGER_CHARGING_SPEED_KEY = "charging_speed"
CHARGER_CHARGING_TIME_KEY = "charging_time"
CHARGER_COST_KEY = "cost"
CHARGER_CURRENT_MODE_KEY = "current_mode"
CHARGER_CURRENT_VERSION_KEY = "currentVersion"
CHARGER_CURRENCY_KEY = "currency"
CHARGER_DATA_KEY = "config_data"
CHARGER_DEPOT_PRICE_KEY = "depot_price"
CHARGER_ENERGY_PRICE_KEY = "energy_price"
CHARGER_SERIAL_NUMBER_KEY = "serial_number"
CHARGER_PART_NUMBER_KEY = "part_number"
CHARGER_SOFTWARE_KEY = "software"
CHARGER_MAX_AVAILABLE_POWER_KEY = "max_available_power"
CHARGER_MAX_CHARGING_CURRENT_KEY = "max_charging_current"
CHARGER_PAUSE_RESUME_KEY = "paused"
CHARGER_LOCKED_UNLOCKED_KEY = "locked"
CHARGER_NAME_KEY = "name"
CHARGER_STATE_OF_CHARGE_KEY = "state_of_charge"
CHARGER_STATUS_ID_KEY = "status_id"
CHARGER_STATUS_DESCRIPTION_KEY = "status_description"
CHARGER_CONNECTIONS = "connections"


class ChargerStatus(StrEnum):
    """Charger Status Description."""

    CHARGING = "Charging"
    DISCHARGING = "Discharging"
    PAUSED = "Paused"
    SCHEDULED = "Scheduled"
    WAITING_FOR_CAR = "Waiting for car demand"
    WAITING = "Waiting"
    DISCONNECTED = "Disconnected"
    ERROR = "Error"
    READY = "Ready"
    LOCKED = "Locked"
    LOCKED_CAR_CONNECTED = "Locked, car connected"
    UPDATING = "Updating"
    WAITING_IN_QUEUE_POWER_SHARING = "Waiting in queue by Power Sharing"
    WAITING_IN_QUEUE_POWER_BOOST = "Waiting in queue by Power Boost"
    WAITING_MID_FAILED = "Waiting MID failed"
    WAITING_MID_SAFETY = "Waiting MID safety margin exceeded"
    WAITING_IN_QUEUE_ECO_SMART = "Waiting in queue by Eco-Smart"
    UNKNOWN = "Unknown"
