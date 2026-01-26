"""Constants for the TFA.me station integration."""

DOMAIN = "tfa_me"
DEFAULT_STATION_NAME = "TFA.me Station"
CONF_NAME_WITH_STATION_ID = "name_with_station_id"
LOCAL_POLL_INTERVAL = 60

MEASUREMENT_TO_TRANSLATION_KEY = {
    "temperature": "temperature",
    "temperature_probe": "temperature",
    "humidity": "humidity",
    "co2": "co2",
    "barometric_pressure": "barometric_pressure",
    "rssi": "rssi",
    "lowbatt": "lowbatt",
    "wind_direction": "wind_direction",
    "wind_direction_deg": "wind_direction",
    "wind_speed": "wind_speed",
    "wind_gust": "wind_gust",
    "rain": "rain",
    "rain_rel": "rain_relative",
    "rain_1_hour": "rain_1_hour",
    "rain_24_hours": "rain_24_hours",
}

# Short description of all stations & sensors
DEVICE_MAPPING = {
    # Stations
    "01": "Station 01: T/H",
    "02": "Station 02: T/H",
    "03": "Station 03: T/H",
    "04": "Station 04: T/H",
    "05": "Station 05: T/H/BP",
    "06": "Station 06: T/H",
    "07": "Station 07: T/H",
    "08": "Station 08: T/H",
    "09": "Station 09: T/H",
    # Debug station ID
    "99": "Station 99: T/H/BP/CO2",
    # Sensors
    "A0": "Sensor A0: T/H",
    "A1": "Sensor A1: Rain",
    "A2": "Sensor A2: Wind: D/W/G",
    "A3": "Sensor A3: T/TP",
    "A4": "Sensor Prof. A4: T/H/TP",
    "A5": "Sensor A5: T",
    "A6": "Sensor Prof. A6: T/H",
}

# Timeout time to mark sensor values "old"/unavailable
# Rule: Timeout time = 2 * (transmission interval in seconds) + 30
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

# Valid JSON keys
VALID_JSON_KEYS = [
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

# Rain sub keys
RAIN_KEYS = ("_rain_1_hour", "_rain_24_hours")
