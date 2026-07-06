"""Sensor platform for the Sifely smart lock integration."""

from __future__ import annotations

from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SifelyConfigEntry, SifelyDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SifelyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sifely sensor platform from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        SifelyBatterySensor(coordinator, lock_id) for lock_id in coordinator.data
    )


class SifelyBatterySensor(
    CoordinatorEntity[SifelyDataUpdateCoordinator], SensorEntity
):
    """Battery level sensor for a Sifely smart lock."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator: SifelyDataUpdateCoordinator, lock_id: int
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator)
        self._lock_id = lock_id
        self._attr_unique_id = f"{lock_id}_battery"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(lock_id))}
        )

    @property
    def _data(self) -> dict[str, Any]:
        """Return this lock's coordinator data."""
        return self.coordinator.data.get(self._lock_id, {})

    @property
    @override
    def available(self) -> bool:
        """Return True if the lock is present in the latest update."""
        return super().available and self._lock_id in self.coordinator.data

    @property
    @override
    def native_value(self) -> int | None:
        """Return the battery level percentage."""
        detail = self._data.get("detail", {})
        info = self._data.get("info", {})
        return detail.get("electricQuantity", info.get("electricQuantity"))
