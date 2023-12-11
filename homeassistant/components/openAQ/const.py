"""Define constants for OpenAQ integration."""

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import Platform

DOMAIN = "openAQ"

API_KEY_ID = "api_id"
LOCATION_ID = "location_id"
THIRD_FIELD = "test"
COUNTRY = "country"
LOCATION = "location"

SENSOR = "sensor"

# All parameters we are searching for in the response we get from a station
OPENAQ_PARAMETERS = {
    "pm25": SensorDeviceClass.PM25,
    "pm10": SensorDeviceClass.PM10,
    "pm1": SensorDeviceClass.PM1,
    "o3": SensorDeviceClass.OZONE,
    "pressure": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
    "temperature": SensorDeviceClass.TEMPERATURE,
    "relativehumidity": SensorDeviceClass.HUMIDITY,
    "no2": SensorDeviceClass.NITROGEN_DIOXIDE,
    "no": SensorDeviceClass.NITROGEN_MONOXIDE,
    "co": SensorDeviceClass.CO,
    "co2": SensorDeviceClass.CO2,
    "so2": SensorDeviceClass.SULPHUR_DIOXIDE,
    "last_update": SensorDeviceClass.TIMESTAMP,
}


ICON_AIR = "mdi:air-filter"
ICON_TIME = "mdi:clock-time-four-outline"

PLATFORMS = [
    Platform.SENSOR,
]
