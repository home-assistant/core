"""Support for the OpenWeatherMap (OWM) service."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ATTR_API_FORECAST,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
    FORECAST_SENSOR_TYPES,
    MANUFACTURER,
    WEATHER_SENSOR_TYPES,
)
from .weather_update_coordinator import WeatherUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OpenWeatherMap sensor entities based on a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    name = domain_data[ENTRY_NAME]
    weather_coordinator = domain_data[ENTRY_WEATHER_COORDINATOR]

    entities: list[AbstractOpenWeatherMapSensor] = [
        OpenWeatherMapSensor(
            name,
            f"{config_entry.unique_id}-{description.key}",
            description,
            weather_coordinator,
        )
        for description in WEATHER_SENSOR_TYPES
    ]

    entities.extend(
        [
            OpenWeatherMapForecastSensor(
                f"{name} Forecast",
                f"{config_entry.unique_id}-forecast-{description.key}",
                description,
                weather_coordinator,
            )
            for description in FORECAST_SENSOR_TYPES
        ]
    )

    async_add_entities(entities)


class AbstractOpenWeatherMapSensor(SensorEntity):
    """Abstract class for an OpenWeatherMap sensor."""

    _attr_should_poll = False
    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    def __init__(
        self,
        name: str,
        unique_id: str,
        description: SensorEntityDescription,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._coordinator = coordinator

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = unique_id
        split_unique_id = unique_id.split("-")
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{split_unique_id[0]}-{split_unique_id[1]}")},
            manufacturer=MANUFACTURER,
            name=DEFAULT_NAME,
        )

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Get the latest data from OWM and updates the states."""
        await self._coordinator.async_request_refresh()


class OpenWeatherMapSensor(AbstractOpenWeatherMapSensor):
    """Implementation of an OpenWeatherMap sensor."""

    def __init__(
        self,
        name: str,
        unique_id: str,
        description: SensorEntityDescription,
        weather_coordinator: WeatherUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(name, unique_id, description, weather_coordinator)
        self._weather_coordinator = weather_coordinator

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        return self._weather_coordinator.data.get(self.entity_description.key, None)


class OpenWeatherMapForecastSensor(AbstractOpenWeatherMapSensor):
    """Implementation of an OpenWeatherMap this day forecast sensor."""

    def __init__(
        self,
        name: str,
        unique_id: str,
        description: SensorEntityDescription,
        weather_coordinator: WeatherUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(name, unique_id, description, weather_coordinator)
        self._weather_coordinator = weather_coordinator

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        forecasts = self._weather_coordinator.data.get(ATTR_API_FORECAST)
        if forecasts is not None and len(forecasts) > 0:
            return forecasts[0].get(self.entity_description.key, None)
        return None
