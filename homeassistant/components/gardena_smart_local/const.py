"""Constants for the GARDENA smart local integration."""

DOMAIN = "gardena_smart_local"

DEFAULT_PORT = 8443

DEFAULT_VALVE_DURATION_MINUTES = 30

# Subentry data key holding {str(valve_id): minutes} for a device's valves
CONF_VALVE_DURATIONS = "valve_durations"
