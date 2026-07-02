"""Constants for the TFA.me station integration."""

DOMAIN = "tfa_me"
DEFAULT_STATION_NAME = "TFA.me Station"
LOCAL_POLL_INTERVAL = 60


# Timeout time to mark sensor values "old"/unavailable
# Rule: Timeout time = 2 * (transmission interval in seconds) + 30
# Availability timeouts are an integration policy (not part of TFA.me protocol).
# These defaults may become user-configurable in a future options flow.
TIMEOUT_FOR_1_MIN = 150
TIMEOUT_FOR_5_MIN = 630
TIMEOUT_FOR_120_MIN = 14430

TIMEOUT_MAPPING = {
    # Stations
    "01": TIMEOUT_FOR_5_MIN,
    "02": TIMEOUT_FOR_5_MIN,
    "03": TIMEOUT_FOR_5_MIN,
    "04": TIMEOUT_FOR_5_MIN,
    "05": TIMEOUT_FOR_5_MIN,
    "06": TIMEOUT_FOR_5_MIN,
    "07": TIMEOUT_FOR_5_MIN,
    "08": TIMEOUT_FOR_5_MIN,
    "09": TIMEOUT_FOR_5_MIN,
    # Debug station ID
    "99": TIMEOUT_FOR_5_MIN,
    # Sensors
    "A0": TIMEOUT_FOR_5_MIN,  # Sensor A0: T/H
    "A1": TIMEOUT_FOR_120_MIN,  # Sensor A1: Rain
    "A2": TIMEOUT_FOR_5_MIN,  # Sensor A2: Wind: D/W/G
    "A3": TIMEOUT_FOR_5_MIN,  # Sensor A3: T/TP
    "A4": TIMEOUT_FOR_1_MIN,  # Sensor Prof. A4: T/H/TP
    "A5": TIMEOUT_FOR_5_MIN,  # Sensor A5: T
    "A6": TIMEOUT_FOR_1_MIN,  # Sensor Prof. A6: T/H
}

# Valid JSON measurement keys
VALID_JSON_MEASUREMENT_KEYS = [
    "temperature",
    "temperature_probe",
    "humidity",
    "co2",
    "barometric_pressure",
    "rssi",
    "lowbatt",
    "wind_direction",
    "wind_speed",
    "wind_gust",
    "rain",
]
