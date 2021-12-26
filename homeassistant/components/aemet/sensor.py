"""Support for the AEMET OpenData service."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
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
    WEATHER_SENSOR_TYPES,
)
from .weather_update_coordinator import WeatherUpdateCoordinator


async def async_setup_entry(hass, config_entry, async_add_entities):
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
                name_prefix,
                unique_id_prefix,
                weather_coordinator,
                mode,
                description,
            )
            for mode in FORECAST_MODES
            if (
                (name_prefix := f"{domain_data[ENTRY_NAME]} {mode} Forecast")
                and (unique_id_prefix := f"{unique_id}-forecast-{mode}")
            )
            for description in FORECAST_SENSOR_TYPES
            if description.key in FORECAST_MONITORED_CONDITIONS
        ]
    )

    async_add_entities(entities)


class AbstractAemetSensor(CoordinatorEntity, SensorEntity):
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
        unique_id,
        weather_coordinator: WeatherUpdateCoordinator,
        description: SensorEntityDescription,
    ):
        """Initialize the sensor."""
        super().__init__(
            name=name,
            unique_id=f"{unique_id}-{description.key}",
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
        unique_id,
        weather_coordinator: WeatherUpdateCoordinator,
        forecast_mode,
        description: SensorEntityDescription,
    ):
        """Initialize the sensor."""
        super().__init__(
            name=name,
            unique_id=f"{unique_id}-{description.key}",
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
        return forecast
