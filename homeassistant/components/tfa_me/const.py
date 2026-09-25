"""Constants for the TFA.me station integration."""

DOMAIN = "tfa_me"
DEFAULT_STATION_NAME = "TFA.me Station"
LOCAL_POLL_INTERVAL = 60

# List with all valid JSON measurement keys this integration can process.
VALID_JSON_MEASUREMENT_KEYS = [
    "temperature",
    "temperature_probe",
    "humidity",
    "co2",
    "barometric_pressure",
    "rssi",
    "lowbatt",
    "wind_direction",
    "wind_direction_deg",
    "wind_speed",
    "wind_gust",
    "rain",
]
