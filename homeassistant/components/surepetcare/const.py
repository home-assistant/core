"""Constants for the Sure Petcare component."""
from datetime import timedelta

DOMAIN = "surepetcare"
DEFAULT_DEVICE_CLASS = "lock"
DEFAULT_ICON = "mdi:cat"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=3)

DATA_SURE_PETCARE = f"data_{DOMAIN}"
SPC = "spc"
SUREPY = "surepy"

CONF_HOUSEHOLD_ID = "household_id"
CONF_FEEDERS = "feeders"
CONF_FLAPS = "flaps"
CONF_PARENT = "parent"
CONF_PETS = "pets"
CONF_PRODUCT_ID = "product_id"
CONF_DATA = "data"

SURE_IDS = "sure_ids"

# platforms
TOPIC_UPDATE = f"{DOMAIN}_data_update"

# sure petcare api
SURE_API_TIMEOUT = 15

# flap
BATTERY_ICON = "mdi:battery"
SURE_BATT_VOLTAGE_FULL = 1.6  # voltage
SURE_BATT_VOLTAGE_LOW = 1.25  # voltage
SURE_BATT_VOLTAGE_DIFF = SURE_BATT_VOLTAGE_FULL - SURE_BATT_VOLTAGE_LOW
