"""Support for Meteoclimatic weather service."""
from meteoclimatic import Condition

from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTRIBUTION, CONDITION_CLASSES, DOMAIN


def format_condition(condition):
    """Return condition from dict CONDITION_CLASSES."""
    for key, value in CONDITION_CLASSES.items():
        if condition in value:
            return key
    if isinstance(condition, Condition):
        return condition.value
    return condition


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Meteoclimatic weather platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([MeteoclimaticWeather(hass_data)], False)


class MeteoclimaticWeather(CoordinatorEntity, WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, coordinator: DataUpdateCoordinator):
        """Initialise the weather platform."""
        super().__init__(coordinator)
        self._unique_id = self.coordinator.data["station"].code
        self._name = self.coordinator.data["station"].name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return self._unique_id

    @property
    def condition(self):
        """Return the current condition."""
        return format_condition(self.coordinator.data["weather"].condition)

    @property
    def temperature(self):
        """Return the temperature."""
        return self.coordinator.data["weather"].temp_current

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def humidity(self):
        """Return the humidity."""
        return self.coordinator.data["weather"].humidity_current

    @property
    def pressure(self):
        """Return the pressure."""
        return self.coordinator.data["weather"].pressure_current

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self.coordinator.data["weather"].wind_current

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self.coordinator.data["weather"].wind_bearing

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION
