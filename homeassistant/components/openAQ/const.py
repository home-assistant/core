"""Define constants for OpenAQ integration."""

from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.const import Platform

DOMAIN = "openAQ"
SENSOR_ID = "sensorid"
DEFAULT_SENSOR_ID = "1234"

API_KEY_ID = "apiid"
CITY_ID = "cityid"
LOCATION_ID = "locationid"

SENSOR = "sensor"
OPENAQ_PARAMETERS = {
    "pm25":SensorDeviceClass.PM25,
    "pm10":SensorDeviceClass.PM10,
    "pm1":SensorDeviceClass.PM1,
    "o3":SensorDeviceClass.OZONE,
    "pressure":SensorDeviceClass.ATMOSPHERIC_PRESSURE,
    "temperature":SensorDeviceClass.TEMPERATURE,
    "relativehumidity":SensorDeviceClass.HUMIDITY,
    "no2":SensorDeviceClass.NITROGEN_DIOXIDE,
    "no":SensorDeviceClass.NITROGEN_MONOXIDE,
    "co":SensorDeviceClass.CO,
    "co2":SensorDeviceClass.CO2,
    "so2":SensorDeviceClass.SULPHUR_DIOXIDE
}


ICON = "mdi:air-filter"

PLATFORMS = [
    Platform.SENSOR,
]
