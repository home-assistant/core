"""Constants for the WeatherflowCloud integration."""
import logging

DOMAIN = "weatherflow_cloud"
_LOGGER = logging.getLogger(__package__)

CONF_STATION_ID = "station_id"
CONF_DEVICE_ID = "device_id"
CONF_FIRMWARE_REVISION = "firmware_revision"
CONF_SERIAL_NUMBER = "serial_number"


ATTR_ATTRIBUTION = "Weather data delivered by WeatherFlow"
ATTR_DESCRIPTION = "description"
ATTR_HW_FIRMWARE_REVISION = "Firmware Revision"
ATTR_HW_SERIAL_NUMBER = "Serial Number"
ATTR_HW_STATION_ID = "Station ID"

DEFAULT_NAME = "WeatherFlow Forecast"

MANUFACTURER = "WeatherFlow"
MODEL = "Rest API"
