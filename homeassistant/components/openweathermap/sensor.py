"""Support for the OpenWeatherMap (OWM) service."""
import logging

from homeassistant.const import (
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    SPEED_METERS_PER_SECOND,
    UNIT_PERCENTAGE,
)

from .abstract_owm_sensor import AbstractOpenWeatherMapSensor
from .const import (
    ATTR_API_CLOUDS,
    ATTR_API_CONDITION,
    ATTR_API_HUMIDITY,
    ATTR_API_PRESSURE,
    ATTR_API_RAIN,
    ATTR_API_SNOW,
    ATTR_API_TEMPERATURE,
    ATTR_API_THIS_DAY_FORECAST,
    ATTR_API_WEATHER,
    ATTR_API_WEATHER_CODE,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_SPEED,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    DOMAIN,
    ENTRY_FORECAST_COORDINATOR,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
    FORECAST_MONITORED_CONDITIONS,
    MONITORED_CONDITIONS,
    SENSOR_DEVICE_CLASS,
    SENSOR_NAME,
    SENSOR_UNIT,
)
from .forecast_update_coordinator import ForecastUpdateCoordinator
from .weather_update_coordinator import WeatherUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up OpenWeatherMap sensor entities based on a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    name = domain_data[ENTRY_NAME]
    weather_coordinator = domain_data[ENTRY_WEATHER_COORDINATOR]
    forecast_coordinator = domain_data[ENTRY_FORECAST_COORDINATOR]

    weather_sensor_types = _get_weather_sensor_types(hass.config.units)
    forecast_sensor_types = _get_forecast_sensor_types(hass.config.units)

    entities = []
    for sensor_type in MONITORED_CONDITIONS:
        unique_id = f"{config_entry.unique_id}-{sensor_type}"
        entities.append(
            OpenWeatherMapSensor(
                name,
                unique_id,
                sensor_type,
                weather_sensor_types[sensor_type],
                weather_coordinator,
            )
        )

    for sensor_type in FORECAST_MONITORED_CONDITIONS:
        unique_id = f"{config_entry.unique_id}-forecast-{sensor_type}"
        entities.append(
            OpenWeatherMapForecastSensor(
                f"{name} Forecast",
                unique_id,
                sensor_type,
                forecast_sensor_types[sensor_type],
                forecast_coordinator,
            )
        )

    async_add_entities(entities, False)


class OpenWeatherMapSensor(AbstractOpenWeatherMapSensor):
    """Implementation of an OpenWeatherMap sensor."""

    def __init__(
        self,
        name,
        unique_id,
        sensor_type,
        sensor_configuration,
        weather_coordinator: WeatherUpdateCoordinator,
    ):
        """Initialize the sensor."""
        super().__init__(
            name, unique_id, sensor_type, sensor_configuration, weather_coordinator
        )
        self._weather_coordinator = weather_coordinator

    @property
    def state(self):
        """Return the state of the device."""
        return self._weather_coordinator.data.get(self._sensor_type, None)


class OpenWeatherMapForecastSensor(AbstractOpenWeatherMapSensor):
    """Implementation of an OpenWeatherMap this day forecast sensor."""

    def __init__(
        self,
        name,
        unique_id,
        sensor_type,
        sensor_configuration,
        forecast_coordinator: ForecastUpdateCoordinator,
    ):
        """Initialize the sensor."""
        super().__init__(
            name, unique_id, sensor_type, sensor_configuration, forecast_coordinator
        )
        self._forecast_coordinator = forecast_coordinator

    @property
    def state(self):
        """Return the state of the device."""
        return self._forecast_coordinator.data[ATTR_API_THIS_DAY_FORECAST].get(
            self._sensor_type, None
        )


def _get_weather_sensor_types(units):
    return {
        ATTR_API_WEATHER: {
            SENSOR_NAME: "Weather",
            SENSOR_UNIT: None,
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_TEMPERATURE: {
            SENSOR_NAME: "Temperature",
            SENSOR_UNIT: units.temperature_unit,
            SENSOR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        },
        ATTR_API_WIND_SPEED: {
            SENSOR_NAME: "Wind speed",
            SENSOR_UNIT: SPEED_METERS_PER_SECOND,
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_WIND_BEARING: {
            SENSOR_NAME: "Wind bearing",
            SENSOR_UNIT: DEGREE,
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_HUMIDITY: {
            SENSOR_NAME: "Humidity",
            SENSOR_UNIT: UNIT_PERCENTAGE,
            SENSOR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        },
        ATTR_API_PRESSURE: {
            SENSOR_NAME: "Pressure",
            SENSOR_UNIT: units.pressure_unit,
            SENSOR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
        },
        ATTR_API_CLOUDS: {
            SENSOR_NAME: "Cloud coverage",
            SENSOR_UNIT: UNIT_PERCENTAGE,
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_RAIN: {
            SENSOR_NAME: "Rain",
            SENSOR_UNIT: "mm",
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_SNOW: {
            SENSOR_NAME: "Snow",
            SENSOR_UNIT: "mm",
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_CONDITION: {
            SENSOR_NAME: "Condition",
            SENSOR_UNIT: None,
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_WEATHER_CODE: {
            SENSOR_NAME: "Weather Code",
            SENSOR_UNIT: None,
            SENSOR_DEVICE_CLASS: None,
        },
    }


def _get_forecast_sensor_types(units):
    return {
        ATTR_FORECAST_CONDITION: {
            SENSOR_NAME: "Condition",
            SENSOR_UNIT: None,
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_FORECAST_PRECIPITATION: {
            SENSOR_NAME: "Precipitation",
            SENSOR_UNIT: None,
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_FORECAST_TEMP: {
            SENSOR_NAME: "Temperature",
            SENSOR_UNIT: units.temperature_unit,
            SENSOR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        },
        ATTR_FORECAST_TEMP_LOW: {
            SENSOR_NAME: "Temperature Low",
            SENSOR_UNIT: units.temperature_unit,
            SENSOR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        },
        ATTR_FORECAST_TIME: {
            SENSOR_NAME: "Time",
            SENSOR_UNIT: None,
            SENSOR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
        },
        ATTR_API_WIND_BEARING: {
            SENSOR_NAME: "Wind bearing",
            SENSOR_UNIT: DEGREE,
            SENSOR_DEVICE_CLASS: None,
        },
        ATTR_API_WIND_SPEED: {
            SENSOR_NAME: "Wind speed",
            SENSOR_UNIT: SPEED_METERS_PER_SECOND,
            SENSOR_DEVICE_CLASS: None,
        },
    }
