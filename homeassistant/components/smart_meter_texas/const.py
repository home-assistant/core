"""Constants for the Smart Meter Texas integration."""
from datetime import timedelta

SCAN_INTERVAL = timedelta(hours=1)
DEBOUNCE_COOLDOWN = 1800  # Seconds

DOMAIN = "smart_meter_texas"

METER_NUMBER = "meter_number"
ESIID = "electric_service_identifier"
LAST_UPDATE = "last_updated"
ELECTRIC_METER = "Electric Meter"
