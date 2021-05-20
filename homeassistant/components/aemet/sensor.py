"""Support for the AEMET OpenData service."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    DOMAIN,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
    FORECAST_MODE_ATTR_API,
    FORECAST_MODE_DAILY,
    FORECAST_MODES,
    FORECAST_MONITORED_CONDITIONS,
    FORECAST_SENSOR_TYPES,
    MONITORED_CONDITIONS,
    SENSOR_DEVICE_CLASS,
    SENSOR_NAME,
    SENSOR_UNIT,
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


class AbstractAemetSensor(CoordinatorEntity, SensorEntity):
    """Abstract class for an AEMET OpenData sensor."""

    def __init__(
        self,
        name,
        unique_id,
        sensor_type,
        sensor_configuration,
        coordinator: WeatherUpdateCoordinator,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._name = name
        self._unique_id = unique_id
        self._sensor_type = sensor_type
        self._sensor_name = sensor_configuration[SENSOR_NAME]
        self._unit_of_measurement = sensor_configuration.get(SENSOR_UNIT)
        self._device_class = sensor_configuration.get(SENSOR_DEVICE_CLASS)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._sensor_name}"

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def device_class(self):
        """Return the device_class."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}


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
        forecast = None
        forecasts = self._weather_coordinator.data.get(
            FORECAST_MODE_ATTR_API[self._forecast_mode]
        )
        if forecasts:
            forecast = forecasts[0].get(self._sensor_type)
        return forecast
