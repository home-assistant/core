"""Constants used by the Sure Petcare component."""
from datetime import timedelta

DOMAIN = "surepetcare"

DEFAULT_DEVICE_CLASS = "door"
DEFAULT_ICON = "mdi:cat"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
DEFAULT_TIMEOUT = 10

CONF_HOUSEHOLD_ID = "household_id"
CONF_FLAPS = "flaps"
CONF_PETS = "pets"

TOPIC_UPDATE = f"{DOMAIN}_data_update"

DATA_SURE_PETCARE = f"data_{DOMAIN}"
DATA_SURE_HOUSEHOLD_NAME = "household_name"
DATA_SURE_LISTENER = "listener"
DATA_SUREPY = "surepy"
DATA_SURE_DATA = "data"

SURE_IDS = "sure_ids"
SURE_TYPES = [CONF_FLAPS, CONF_PETS]
