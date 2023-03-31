"""Support for the HKO service."""
from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    API_CONDITION,
    API_CURRENT,
    API_FORECAST,
    API_HUMIDITY,
    API_TEMPERATURE,
    ATTRIBUTION,
    CONF_LOCATION,
    DOMAIN,
    MANUFACTURER,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a HKO weather entity from a config_entry."""
    name = config_entry.data[CONF_LOCATION]
    unique_id = config_entry.unique_id
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([HKOEntity(name, unique_id, coordinator)], False)


class HKOEntity(CoordinatorEntity, WeatherEntity):
    """Define a HKO entity."""

    def __init__(self, name, unique_id, coordinator: DataUpdateCoordinator) -> None:
        """Initialise the weather platform."""
        super().__init__(coordinator)
        self._name = name
        self._unique_id = unique_id

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def unique_id(self) -> str:
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "manufacturer": MANUFACTURER,
            "entry_type": DeviceEntryType.SERVICE,
        }

    @property
    def condition(self) -> str:
        """Return the current condition."""
        return self.coordinator.data[API_FORECAST][0][API_CONDITION]

    @property
    def native_temperature(self) -> int:
        """Return the temperature."""
        return self.coordinator.data[API_CURRENT][API_TEMPERATURE]

    @property
    def native_temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def humidity(self) -> int:
        """Return the humidity."""
        return self.coordinator.data[API_CURRENT][API_HUMIDITY]

    @property
    def forecast(self) -> list:
        """Return the forecast array."""
        return self.coordinator.data[API_FORECAST]
