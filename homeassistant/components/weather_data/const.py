"""Constants for the Weather data integration."""

from homeassistant.components.sensor import SensorDeviceClass

DOMAIN = "weather_data"

# Integrations in this manifest category provide air quality and pollen
AIR_QUALITY_CATEGORY = "weather_alerts.air_quality_pollen"

# One sensor per device class is used, in this order
AIR_QUALITY_DEVICE_CLASSES = (
    SensorDeviceClass.AQI,
    SensorDeviceClass.PM25,
    SensorDeviceClass.PM10,
    SensorDeviceClass.NITROGEN_DIOXIDE,
    SensorDeviceClass.OZONE,
)
