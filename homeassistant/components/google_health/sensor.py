"""Sensor platform for the Google Health integration."""

from typing import override

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GoogleHealthConfigEntry, GoogleHealthCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleHealthConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Google Health sensor platform."""
    coordinator = entry.runtime_data

    async_add_entities([GoogleHealthStepsSensor(coordinator, entry.entry_id)])


class GoogleHealthStepsSensor(CoordinatorEntity[GoogleHealthCoordinator], SensorEntity):
    """Steps sensor entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "steps"
    _attr_native_unit_of_measurement = "steps"
    _attr_icon = "mdi:walk"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: GoogleHealthCoordinator, entry_id: str) -> None:
        """Initialize the steps sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_steps"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Google Health",
            manufacturer="Google",
        )

    @property
    @override
    def native_value(self) -> int:
        """Return the steps count."""
        return self.coordinator.data
