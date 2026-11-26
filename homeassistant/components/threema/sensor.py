"""Sensor platform for Threema Gateway integration."""

from typing import override

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThreemaConfigEntry, ThreemaCreditsCoordinator

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThreemaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Threema Gateway credits sensor."""
    async_add_entities([ThreemaCreditsSensor(entry.runtime_data)])


class ThreemaCreditsSensor(CoordinatorEntity[ThreemaCreditsCoordinator], SensorEntity):
    """Sensor for the remaining credits of a Threema Gateway account."""

    _attr_has_entity_name = True
    _attr_translation_key = "credits"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ThreemaCreditsCoordinator) -> None:
        """Initialize the credits sensor."""
        super().__init__(coordinator)
        gateway_id = coordinator.client.gateway_id

        self._attr_unique_id = f"{gateway_id}_credits"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Threema",
            model="Gateway",
            identifiers={(DOMAIN, gateway_id)},
            name=coordinator.config_entry.title,
        )

    @property
    @override
    def native_value(self) -> int:
        """Return the remaining credits."""
        return self.coordinator.data
