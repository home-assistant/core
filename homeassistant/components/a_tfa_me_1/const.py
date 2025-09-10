"""Constants for the TFA.me station integration."""

DOMAIN = "a_tfa_me_1"
DEFAULT_NAME = "TFA.me Station"
CONF_INTERVAL = "interval"
CONF_MULTIPLE_ENTITIES = "multiple_entities"

# Used icons for entities, see also
# https://pictogrammers.com/library/mdi/
ICON_MAPPING = {
    "temperature": {
        "default": "mdi:thermometer",
        "high": "mdi:thermometer-high",
        "low": "mdi:thermometer-low",
    },
    "humidity": {"default": "mdi:water-percent", "alert": "mdi:water-percent-alert"},
    "co2": {"default": "mdi:molecule-co2"},
    "barometric_pressure": {"default": "mdi:gauge"},
    "rssi": {
        "default": "mdi:wifi",
        "weak": "mdi:wifi-strength-1",
        "middle": "mdi:wifi-strength-2",
        "good": "mdi:wifi-strength-3",
        "strong": "mdi:wifi-strength-4",
    },
    "lowbatt": {
        "default": "mdi:battery",
        "low": "mdi:battery-alert",
        "full": "mdi:battery",
    },
    "wind_direction": {"default": "mdi:compass-outline"},
    "wind": {
        "default": "mdi:weather-windy",
        "wind": "mdi:weather-windy-variant",
        "gust": "mdi:weather-windy",
    },
    "rain": {
        "none": "mdi:weather-sunny",
        "light": "mdi:weather-partly-rainy",
        "moderate": "mdi:weather-rainy",
        "heavy": "mdi:weather-pouring",
    },
}

ICON_MAPPING_WIND_DIR = {
    "0": "mdi:arrow-down",  # N (North)
    "1": "mdi:arrow-down",  # N (North)
    "2": "mdi:arrow-bottom-left",  # NE (North-East)
    "3": "mdi:arrow-bottom-left",  # NE (North-East)
    "4": "mdi:arrow-left",  # E (East)
    "5": "mdi:arrow-left",  # E (East)
    "6": "mdi:arrow-top-left",  # SE (South-East)
    "7": "mdi:arrow-top-left",  # SE (South-East)
    "8": "mdi:arrow-up",  # S (South)
    "9": "mdi:arrow-up",  # S (South)
    "10": "mdi:arrow-top-right",  # SW (South-West)
    "11": "mdi:arrow-top-right",  # SW (South-West)
    "12": "mdi:arrow-right",  # W (West)
    "13": "mdi:arrow-right",  # W (West)
    "14": "mdi:arrow-bottom-right",  # NW (North-West)
    "15": "mdi:arrow-bottom-right",  # NW (North-West)
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
    # Add other stations here ...
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
    # Add other sensors here ...
}

# Timeout time use sensor marked "old"/unavailable
# Rule: Timeout time = 2 * (transmission interval in seconds) + 30
TIMEOUT_FOR_1_MIN = (2 * 1 * 60) + 30
TIMEOUT_FOR_5_MIN = (2 * 5 * 60) + 30
TIMEOUT_FOR_120_MIN = (2 * 120 * 60) + 30

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
    # Add other stations here ...
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
    # Add other sensors here ...
}
