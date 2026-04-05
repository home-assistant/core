"""Binary sensor entities for Mitsubishi Comfort integration."""

from __future__ import annotations

from mitsubishi_comfort import IndoorUnit

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MitsubishiComfortConfigEntry
from .coordinator import MitsubishiComfortCoordinator
from .entity import MitsubishiComfortEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MitsubishiComfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mitsubishi Comfort binary sensor entities."""
    coordinators = entry.runtime_data
    entities = [
        MitsubishiComfortFilterDirtySensor(coordinator)
        for coordinator in coordinators.values()
        if isinstance(coordinator.device, IndoorUnit)
    ]
    async_add_entities(entities)


class MitsubishiComfortFilterDirtySensor(MitsubishiComfortEntity, BinarySensorEntity):
    """Filter dirty binary sensor — on means filter needs cleaning."""

    def __init__(self, coordinator: MitsubishiComfortCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device.serial}-filter-dirty"
        self._attr_name = "Filter dirty"

    @property
    def is_on(self) -> bool | None:
        """Return true if the filter is dirty."""
        return self._device.status.filter_dirty
