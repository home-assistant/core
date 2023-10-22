"""Constants for the Vevor Heater integration."""
from datetime import timedelta
from uuid import UUID

DOMAIN = "vevor_heater"

CHAR_UUID_HEATER_CONTROL = UUID("0000ffe1-0000-1000-8000-00805f9b34fb")
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=60)
