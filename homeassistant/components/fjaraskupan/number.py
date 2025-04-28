"""Support for sensors."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import async_setup_entry_platform
from .coordinator import FjaraskupanConfigEntry, FjaraskupanCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FjaraskupanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities dynamically through discovery."""

    def _constructor(coordinator: FjaraskupanCoordinator) -> list[Entity]:
        return [
            PeriodicVentingTime(coordinator, coordinator.device_info),
        ]

    async_setup_entry_platform(hass, config_entry, async_add_entities, _constructor)


class PeriodicVentingTime(CoordinatorEntity[FjaraskupanCoordinator], NumberEntity):
    """Periodic Venting."""

    _attr_has_entity_name = True

    _attr_native_max_value: float = 59
    _attr_native_min_value: float = 0
    _attr_native_step: float = 1
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_translation_key = "periodic_venting"

    def __init__(
        self,
        coordinator: FjaraskupanCoordinator,
        device_info: DeviceInfo,
    ) -> None:
        """Init number entities."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}-periodic-venting"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        if data := self.coordinator.data:
            return data.periodic_venting
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        async with self.coordinator.async_connect_and_update() as device:
            await device.send_periodic_venting(int(value))
