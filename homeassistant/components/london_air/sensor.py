"""Sensor platform for the London Air integration."""

from typing import override

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LOCATIONS, DOMAIN, MANUFACTURER
from .coordinator import (
    LondonAirConfigEntry,
    LondonAirDataUpdateCoordinator,
    authority_status,
)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LondonAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up London Air sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        LondonAirSensor(coordinator, authority)
        for authority in entry.data[CONF_LOCATIONS]
    )


class LondonAirSensor(CoordinatorEntity[LondonAirDataUpdateCoordinator], SensorEntity):
    """Sensor reporting the air quality band for a London authority."""

    _attr_has_entity_name = True
    _attr_translation_key = "air_quality"

    def __init__(
        self,
        coordinator: LondonAirDataUpdateCoordinator,
        authority: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._authority = authority
        self._attr_unique_id = authority
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, authority)},
            name=authority,
            manufacturer=MANUFACTURER,
        )
        self._update_attributes()

    def _update_attributes(self) -> None:
        """Set the sensor attributes from the coordinator data."""
        site_data = self.coordinator.data[self._authority]
        self._attr_native_value = authority_status(site_data)
        self._attr_extra_state_attributes = {
            "sites": len(site_data),
            "updated": site_data[0]["updated"] if site_data else None,
            "data": site_data,
        }

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        self.async_write_ha_state()
