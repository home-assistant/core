"""Support for the OpenWeatherMap (OWM) service."""
from .abstract_owm_sensor import AbstractOpenWeatherMapSensor
from .const import (
    ATTR_API_FORECAST,
    DOMAIN,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
    FORECAST_MONITORED_CONDITIONS,
    FORECAST_SENSOR_TYPES,
    MONITORED_CONDITIONS,
    WEATHER_SENSOR_TYPES,
)
from .weather_update_coordinator import WeatherUpdateCoordinator


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up OpenWeatherMap sensor entities based on a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    name = domain_data[ENTRY_NAME]
    weather_coordinator = domain_data[ENTRY_WEATHER_COORDINATOR]

    weather_sensor_types = WEATHER_SENSOR_TYPES
    forecast_sensor_types = FORECAST_SENSOR_TYPES

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
                weather_coordinator,
            )
        )

    async_add_entities(entities)


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
        forecasts = self._weather_coordinator.data.get(ATTR_API_FORECAST)
        if forecasts is not None and len(forecasts) > 0:
            return forecasts[0].get(self._sensor_type, None)
        return None
