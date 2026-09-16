"""Constants for the Eurotronic Comet WiFi integration."""

import logging

DOMAIN = "eurotronic_comet_wifi"
MANUFACTURER = "Eurotronic"
MODEL = "Eurotronic Comet WiFi"
DEVICE_NAME_PREFIX = "Comet WiFi"

LOGGER = logging.getLogger(__package__)

POLL_INTERVAL = 900  # seconds
FETCH_DATA_TIMEOUT = 5  # seconds
DEFAULT_SETPOINT = 20.0  # °C, when turning on before any setpoint was set

UNIQUE_ID_SUFFIX_CLIMATE = "climate"
