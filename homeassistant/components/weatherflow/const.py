"""Constants for the WeatherFlow integration."""

import logging

from homeassistant.config_entries import ConfigEntry

DOMAIN = "weatherflow"
_LOGGER = logging.getLogger(__package__)


def format_dispatch_call(config_entry: ConfigEntry) -> str:
    """Construct a dispatch call from a ConfigEntry."""
    return f"{config_entry.domain}_{config_entry.entry_id}_add"


ERROR_MSG_ADDRESS_IN_USE = "address_in_use"
ERROR_MSG_CANNOT_CONNECT = "cannot_connect"
ERROR_MSG_NO_DEVICE_FOUND = "no_device_found"

CONF_STATION_ID = "station_id"
CONF_FIRMWARE_REVISION = "firmware_revision"
CONF_SERIAL_NUMBER = "serial_number"

CONF_LOCAL_SENSORS = "local_sensors"
CONF_CLOUD_SENSORS = "cloud_sensors"


ATTR_ATTRIBUTION = "Weather data delivered by WeatherFlow"
ATTR_DESCRIPTION = "description"
ATTR_HW_FIRMWARE_REVISION = "Firmware Revision"
ATTR_HW_SERIAL_NUMBER = "Serial Number"
ATTR_HW_STATION_ID = "Station ID"
DEFAULT_NAME = "WeatherFlow Forecast"
MODEL = "Rest API"
MANUFACTURER = "WeatherFlow"
