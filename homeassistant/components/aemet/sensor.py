"""Support for the AEMET OpenData service."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_API_FORECAST_TIME,
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
    WEATHER_SENSOR_TYPES,
)
from .weather_update_coordinator import WeatherUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AEMET OpenData sensor entities based on a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    name = domain_data[ENTRY_NAME]
    weather_coordinator = domain_data[ENTRY_WEATHER_COORDINATOR]

    unique_id = config_entry.unique_id
    entities: list[AbstractAemetSensor] = [
        AemetSensor(name, unique_id, weather_coordinator, description)
        for description in WEATHER_SENSOR_TYPES
        if description.key in MONITORED_CONDITIONS
    ]
    entities.extend(
        [
            AemetForecastSensor(
                f"{domain_data[ENTRY_NAME]} {mode} Forecast",
                f"{unique_id}-forecast-{mode}",
                weather_coordinator,
                mode,
                description,
            )
            for mode in FORECAST_MODES
            for description in FORECAST_SENSOR_TYPES
            if description.key in FORECAST_MONITORED_CONDITIONS
        ]
    )

    async_add_entities(entities)


class AbstractAemetSensor(CoordinatorEntity[WeatherUpdateCoordinator], SensorEntity):
    """Abstract class for an AEMET OpenData sensor."""

    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    def __init__(
        self,
        name,
        unique_id,
        coordinator: WeatherUpdateCoordinator,
        description: SensorEntityDescription,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = unique_id


class AemetSensor(AbstractAemetSensor):
    """Implementation of an AEMET OpenData sensor."""

    def __init__(
        self,
        name,
        unique_id_prefix,
        weather_coordinator: WeatherUpdateCoordinator,
        description: SensorEntityDescription,
    ):
        """Initialize the sensor."""
        super().__init__(
            name=name,
            unique_id=f"{unique_id_prefix}-{description.key}",
            coordinator=weather_coordinator,
            description=description,
        )

    @property
    def native_value(self):
        """Return the state of the device."""
        return self.coordinator.data.get(self.entity_description.key)


class AemetForecastSensor(AbstractAemetSensor):
    """Implementation of an AEMET OpenData forecast sensor."""

    def __init__(
        self,
        name,
        unique_id_prefix,
        weather_coordinator: WeatherUpdateCoordinator,
        forecast_mode,
        description: SensorEntityDescription,
    ):
        """Initialize the sensor."""
        super().__init__(
            name=name,
            unique_id=f"{unique_id_prefix}-{description.key}",
            coordinator=weather_coordinator,
            description=description,
        )
        self._forecast_mode = forecast_mode
        self._attr_entity_registry_enabled_default = (
            self._forecast_mode == FORECAST_MODE_DAILY
        )

    @property
    def native_value(self):
        """Return the state of the device."""
        forecast = None
        forecasts = self.coordinator.data.get(
            FORECAST_MODE_ATTR_API[self._forecast_mode]
        )
        if forecasts:
            forecast = forecasts[0].get(self.entity_description.key)
            if self.entity_description.key == ATTR_API_FORECAST_TIME:
                forecast = dt_util.parse_datetime(forecast)
        return forecast
