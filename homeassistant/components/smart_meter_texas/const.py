"""Constants for the Smart Meter Texas integration."""
from datetime import timedelta

DOMAIN = "smart_meter_texas"
LAST_UPDATED = "last_updated"
SCAN_INTERVAL = timedelta(hours=1)
DEBOUNCE_COOLDOWN = 1800  # Seconds
METER_NUMBER = "meter_number"
