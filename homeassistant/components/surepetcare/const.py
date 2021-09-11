"""Constants for the Sure Petcare component."""
DOMAIN = "surepetcare"

CONF_FEEDERS = "feeders"
CONF_FLAPS = "flaps"
CONF_PETS = "pets"

# sure petcare api
SURE_API_TIMEOUT = 60

# flap
SURE_BATT_VOLTAGE_FULL = 1.6  # voltage
SURE_BATT_VOLTAGE_LOW = 1.25  # voltage
SURE_BATT_VOLTAGE_DIFF = SURE_BATT_VOLTAGE_FULL - SURE_BATT_VOLTAGE_LOW

# lock state service
SERVICE_SET_LOCK_STATE = "set_lock_state"
ATTR_FLAP_ID = "flap_id"
ATTR_LOCK_STATE = "lock_state"
