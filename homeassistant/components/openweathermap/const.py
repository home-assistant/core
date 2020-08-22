"""Constants for OpenWeatherMap integration."""
from homeassistant.const import (  # pylint:disable=unused-import
    ATTR_DEVICE_CLASS,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_METERS,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_HOURS,
    UNIT_PERCENTAGE,
    UV_INDEX,
    VOLUME_CUBIC_METERS,
)  # pylint:disable=unused-import

ATTRIBUTION = "Data provided by OpenWeatherMap"
ATTR_ICON = "icon"
ATTR_FORECAST = CONF_FORECAST = "forecast"
ATTR_LABEL = "label"
ATTR_UNIT_IMPERIAL = "Imperial"
ATTR_UNIT_METRIC = "Metric"
COORDINATOR = "coordinator"
DOMAIN = "openweathermap"
LENGTH_MILIMETERS = "mm"
MANUFACTURER = "Openweather	Ltd."
NAME = DEFAULT_NAME = "OpenWeatherMap"
FORECAST_MODE = ["hourly", "daily", "freedaily"]
