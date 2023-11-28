"""Define constants for OpenAQ integration."""

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import Platform

DOMAIN = "openAQ"
SENSOR_ID = "sensorid"
DEFAULT_SENSOR_ID = "1234"

API_KEY_ID = "api_id"
CITY_ID = "city_id"
LOCATION_ID = "location_id"
THIRD_FIELD = "test"
COUNTRY = "country"
LOCATION = "location"

SENSOR = "sensor"
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


ICON = "mdi:air-filter"

PLATFORMS = [
    Platform.SENSOR,
]
