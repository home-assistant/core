"""Support for sensors."""

from __future__ import annotations

from typing import cast

from aiocomelit import ComelitVedoZoneObject

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ComelitConfigEntry, ComelitVedoSystem
from .utils import DeviceType, new_device_listener

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ComelitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comelit VEDO presence sensors."""

    coordinator = cast(ComelitVedoSystem, config_entry.runtime_data)

    def _add_new_entities(
        new_devices: list[DeviceType], dev_type: str = "not_used"
    ) -> None:
        """Add entities for new monitors."""
        entities = [
            ComelitVedoBinarySensorEntity(coordinator, device, config_entry.entry_id)
            for device in coordinator.data["alarm_zones"].values()
            if device in new_devices
        ]
        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        new_device_listener(coordinator, _add_new_entities, "alarm_zones")
    )


class ComelitVedoBinarySensorEntity(
    CoordinatorEntity[ComelitVedoSystem], BinarySensorEntity
):
    """Sensor device."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(
        self,
        coordinator: ComelitVedoSystem,
        zone: ComelitVedoZoneObject,
        config_entry_entry_id: str,
    ) -> None:
        """Init sensor entity."""
        self._zone_index = zone.index
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-presence-{zone.index}"
        self._attr_device_info = coordinator.platform_device_info(zone, "zone")

    @property
    def is_on(self) -> bool:
        """Presence detected."""
        return (
            self.coordinator.data["alarm_zones"][self._zone_index].status_api == "0001"
        )
