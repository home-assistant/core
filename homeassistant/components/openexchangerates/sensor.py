"""Support for openexchangerates.org exchange rates service."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_QUOTE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenexchangeratesCoordinator

ATTRIBUTION = "Data provided by openexchangerates.org"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Open Exchange Rates sensor."""
    quote: str = config_entry.data.get(CONF_QUOTE, "EUR")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        OpenexchangeratesSensor(
            config_entry, coordinator, rate_quote, rate_quote == quote
        )
        for rate_quote in coordinator.data.rates
    )


class OpenexchangeratesSensor(
    CoordinatorEntity[OpenexchangeratesCoordinator], SensorEntity
):
    """Representation of an Open Exchange Rates sensor."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: OpenexchangeratesCoordinator,
        quote: str,
        enabled: bool,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Open Exchange Rates",
            name=f"Open Exchange Rates {coordinator.base}",
        )
        self._attr_entity_registry_enabled_default = enabled
        self._attr_name = quote
        self._attr_native_unit_of_measurement = quote
        self._attr_unique_id = f"{config_entry.entry_id}_{quote}"
        self._quote = quote

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self.coordinator.data.rates[self._quote]
