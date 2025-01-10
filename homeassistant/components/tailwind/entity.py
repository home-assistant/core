"""Base entity for the Tailwind integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TailwindDataUpdateCoordinator


class TailwindEntity(CoordinatorEntity[TailwindDataUpdateCoordinator]):
    """Defines an Tailwind entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TailwindDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize an Tailwind entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.data.device_id}-{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.device_id)},
        )


class TailwindDoorEntity(CoordinatorEntity[TailwindDataUpdateCoordinator]):
    """Defines an Tailwind door entity.

    These are the entities that belong to a specific garage door opener
    that is connected via the Tailwind controller.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TailwindDataUpdateCoordinator,
        door_id: str,
        entity_description: EntityDescription | None = None,
    ) -> None:
        """Initialize an Tailwind door entity."""
        super().__init__(coordinator)
        self.door_id = door_id

        self._attr_unique_id = f"{coordinator.data.device_id}-{door_id}"
        if entity_description:
            self.entity_description = entity_description
            self._attr_unique_id = (
                f"{coordinator.data.device_id}-{door_id}-{entity_description.key}"
            )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.data.device_id}-{door_id}")},
            via_device=(DOMAIN, coordinator.data.device_id),
            name=f"Door {coordinator.data.doors[door_id].index + 1}",
            manufacturer="Tailwind",
            model=coordinator.data.product,
            sw_version=coordinator.data.firmware_version,
        )
