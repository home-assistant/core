"""Support for Meteoclimatic weather service."""

from meteoclimatic import Condition

from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTRIBUTION, CONDITION_MAP, DOMAIN, MANUFACTURER, MODEL


def format_condition(condition):
    """Return condition from dict CONDITION_MAP."""
    if condition in CONDITION_MAP:
        return CONDITION_MAP[condition]
    if isinstance(condition, Condition):
        return condition.value
    return condition


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Meteoclimatic weather platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([MeteoclimaticWeather(coordinator)], False)


class MeteoclimaticWeather(CoordinatorEntity, WeatherEntity):
    """Representation of a weather condition."""

    _attr_attribution = ATTRIBUTION
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
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
    def device_info(self):
        """Return the device info."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.platform.config_entry.unique_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=self.coordinator.name,
        )

    @property
    def condition(self):
        """Return the current condition."""
        return format_condition(self.coordinator.data["weather"].condition)

    @property
    def native_temperature(self):
        """Return the temperature."""
        return self.coordinator.data["weather"].temp_current

    @property
    def humidity(self):
        """Return the humidity."""
        return self.coordinator.data["weather"].humidity_current

    @property
    def native_pressure(self):
        """Return the pressure."""
        return self.coordinator.data["weather"].pressure_current

    @property
    def native_wind_speed(self):
        """Return the wind speed."""
        return self.coordinator.data["weather"].wind_current

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self.coordinator.data["weather"].wind_bearing
