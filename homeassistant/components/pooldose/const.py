"""Constants for the Seko Pooldose integration."""

DOMAIN = "pooldose"
CONF_SERIALNUMBER = "serialnumber"

DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_SCAN_INTERVAL = 600  # seconds

SENSOR_MAP: dict[str, tuple[str, str | None, str | None, str]] = {
    "pool_temp_actual": (
        "Pool Temperature Actual",
        "°C",
        "temperature",
        "PDPR1H1HAW100_FW539187_w_1eommf39k",
    ),
    "pool_ph_actual": (
        "Pool pH Actual",
        "pH",
        None,
        "PDPR1H1HAW100_FW539187_w_1ekeigkin",
    ),
    "pool_ph_target": (
        "Pool pH Target",
        "pH",
        None,
        "PDPR1H1HAW100_FW539187_w_1ekeiqfat",
    ),
    "pool_orp_actual": (
        "Pool ORP Actual",
        "mV",
        None,
        "PDPR1H1HAW100_FW539187_w_1eklenb23",
    ),
    "pool_orp_target": (
        "Pool ORP Target",
        "mV",
        None,
        "PDPR1H1HAW100_FW539187_w_1eklgnjk2",
    ),
    "pool_circulation_raw": (
        "Pool Circulation Pump raw",
        None,
        None,
        "PDPR1H1HAW100_FW539187_w_1ekga097n",
    ),
    # Add more sensors here as needed
}

SWITCHES: dict[str, tuple[str, str, str, str]] = {
    "stop_pool_dosing": (
        "Stop dosing",
        "PDPR1H1HAW100_FW539187_w_1emtltkel",
        "F",
        "O",
    ),
    # Add more switches here as needed
}

BINARY_SENSOR_MAP: dict[str, tuple[str, str]] = {
    "stop_pool_dosing_state": (
        "Stop Dosing State",
        "PDPR1H1HAW100_FW539187_w_1emtltkel",
    ),
    # Add more binary sensors here as needed
}

# for testing only:
DEFAULT_HOST = "192.168.178.137"
DEFAULT_SERIAL_NUMBER = "01220000095B"
