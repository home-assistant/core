"""Constants for the Seko Pooldose integration."""

DOMAIN = "pooldose"
CONF_SERIALNUMBER = "serialnumber"

DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_SCAN_INTERVAL = 600  # seconds

SENSOR_MAP: dict[str, tuple[str, str | None, str | None, str]] = {
    "pool_temp_ist": (
        "Pool Temperature Actual",
        "°C",
        "temperature",
        "PDPR1H1HAW100_FW539187_w_1eommf39k",
    ),
    "pool_ph_ist": ("Pool pH Actual", "pH", None, "PDPR1H1HAW100_FW539187_w_1ekeigkin"),
    "pool_ph_soll": (
        "Pool pH Target",
        "pH",
        None,
        "PDPR1H1HAW100_FW539187_w_1ekeiqfat",
    ),
    "pool_orp_ist": (
        "Pool ORP Actual",
        "mV",
        None,
        "PDPR1H1HAW100_FW539187_w_1eklenb23",
    ),
    "pool_orp_soll": (
        "Pool ORP Target",
        "mV",
        None,
        "PDPR1H1HAW100_FW539187_w_1eklgnjk2",
    ),
    "pool_zirkulation_raw": (
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
    "pool_dosierung_stop_status": (
        "Stop Pool Dosing Status",
        "PDPR1H1HAW100_FW539187_w_1emtltkel",
    ),
    # Add more binary sensors here as needed
}

# for testing only:
DEFAULT_HOST = "192.168.178.137"
DEFAULT_SERIAL_NUMBER = "01220000095B"
