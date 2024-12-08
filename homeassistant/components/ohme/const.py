"""Component constants."""

DOMAIN = "ohme"
CONFIG_VERSION = 1
ENTITY_TYPES = ["sensor", "binary_sensor", "switch", "button", "number", "time"]

DATA_CLIENT = "client"
DATA_COORDINATORS = "coordinators"
DATA_OPTIONS = "options"
DATA_SLOTS = "slots"

COORDINATOR_CHARGESESSIONS = 0
COORDINATOR_ACCOUNTINFO = 1
COORDINATOR_ADVANCED = 2
COORDINATOR_SCHEDULES = 3

DEFAULT_INTERVAL_CHARGESESSIONS = 0.5
DEFAULT_INTERVAL_ACCOUNTINFO = 1
DEFAULT_INTERVAL_ADVANCED = 1
DEFAULT_INTERVAL_SCHEDULES = 10

LEGACY_MAPPING = {
    "ohme_car_charging": "car_charging",
    "ohme_slot_active": "slot_active",
    "target_percent": "target_percentage",
    "session_energy": "energy",
    "next_slot": "next_slot_start",
    "solarMode": "solar_mode",
    "buttonsLocked": "lock_buttons",
    "pluginsRequireApproval": "require_approval",
    "stealthEnabled": "sleep_when_inactive",
    "price_cap_enabled": "enable_price_cap",
}
