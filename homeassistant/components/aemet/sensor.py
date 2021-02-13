"""Support for the AEMET OpenData service."""
from .abstract_aemet_sensor import AbstractAemetSensor
from .const import (
    DOMAIN,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
    FORECAST_MODE_ATTR_API,
    FORECAST_MODE_DAILY,
    FORECAST_MODES,
    FORECAST_MONITORED_CONDITIONS,
    FORECAST_SENSOR_TYPES,
    MONITORED_CONDITIONS,
    WEATHER_SENSOR_TYPES,
)
from .weather_update_coordinator import WeatherUpdateCoordinator


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AEMET OpenData sensor entities based on a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    name = domain_data[ENTRY_NAME]
    weather_coordinator = domain_data[ENTRY_WEATHER_COORDINATOR]

    weather_sensor_types = WEATHER_SENSOR_TYPES
    forecast_sensor_types = FORECAST_SENSOR_TYPES

    entities = []
    for sensor_type in MONITORED_CONDITIONS:
        unique_id = f"{config_entry.unique_id}-{sensor_type}"
        entities.append(
            AemetSensor(
                name,
                unique_id,
                sensor_type,
                weather_sensor_types[sensor_type],
                weather_coordinator,
            )
        )

    for mode in FORECAST_MODES:
        name = f"{domain_data[ENTRY_NAME]} {mode}"

        for sensor_type in FORECAST_MONITORED_CONDITIONS:
            unique_id = f"{config_entry.unique_id}-forecast-{mode}-{sensor_type}"
            entities.append(
                AemetForecastSensor(
                    f"{name} Forecast",
                    unique_id,
                    sensor_type,
                    forecast_sensor_types[sensor_type],
                    weather_coordinator,
                    mode,
                )
            )

    async_add_entities(entities)


class AemetSensor(AbstractAemetSensor):
    """Implementation of an AEMET OpenData sensor."""

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
        return self._weather_coordinator.data.get(self._sensor_type)


class AemetForecastSensor(AbstractAemetSensor):
    """Implementation of an AEMET OpenData forecast sensor."""

    def __init__(
        self,
        name,
        unique_id,
        sensor_type,
        sensor_configuration,
        weather_coordinator: WeatherUpdateCoordinator,
        forecast_mode,
    ):
        """Initialize the sensor."""
        super().__init__(
            name, unique_id, sensor_type, sensor_configuration, weather_coordinator
        )
        self._weather_coordinator = weather_coordinator
        self._forecast_mode = forecast_mode

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._forecast_mode == FORECAST_MODE_DAILY

    @property
    def state(self):
        """Return the state of the device."""
        forecasts = self._weather_coordinator.data.get(
            FORECAST_MODE_ATTR_API[self._forecast_mode]
        )
        if forecasts:
            return forecasts[0].get(self._sensor_type)
        return None
