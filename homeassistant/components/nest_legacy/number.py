"""Number platform for Nest thermostats."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NestConfigEntry, NestCoordinator
from .entity import NestEntity
from .pynest.models import NestLock

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nest number platform from a config entry."""
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = []
    entities.extend(
        NestLockAutoRelockDuration(coordinator, device)
        for device in coordinator.data.values()
        if isinstance(device, NestLock)
    )
    async_add_devices(entities)


class NestLockAutoRelockDuration(NestEntity[NestLock], NumberEntity):
    """Representation of a Nest Lock Auto-Relock Duration."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_translation_key = "auto_relock_duration"
    _attr_icon = "mdi:timer-lock"

    def __init__(self, coordinator: NestCoordinator, device: NestLock) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.serial_number}-auto_relock_duration"
        self._attr_native_min_value = 0
        self._attr_native_max_value = device.max_auto_relock_duration

    @property
    def native_value(self) -> float | None:
        """Return the entity state."""
        return self.device.auto_relock_duration

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._set_device_data({"auto_relock_duration": int(value)})
