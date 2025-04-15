"""Support for the HKO service."""

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    API_CONDITION,
    API_CURRENT,
    API_FORECAST,
    API_HUMIDITY,
    API_TEMPERATURE,
    ATTRIBUTION,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import HKOUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a HKO weather entity from a config_entry."""
    assert config_entry.unique_id is not None
    unique_id = config_entry.unique_id
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([HKOEntity(unique_id, coordinator)], False)


class HKOEntity(CoordinatorEntity[HKOUpdateCoordinator], WeatherEntity):
    """Define a HKO entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY
    _attr_attribution = ATTRIBUTION

    def __init__(self, unique_id: str, coordinator: HKOUpdateCoordinator) -> None:
        """Initialise the weather platform."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def condition(self) -> str:
        """Return the current condition."""
        return self.coordinator.data[API_FORECAST][0][API_CONDITION]

    @property
    def native_temperature(self) -> int:
        """Return the temperature."""
        return self.coordinator.data[API_CURRENT][API_TEMPERATURE]

    @property
    def humidity(self) -> int:
        """Return the humidity."""
        return self.coordinator.data[API_CURRENT][API_HUMIDITY]

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the forecast data."""
        return self.coordinator.data[API_FORECAST]
