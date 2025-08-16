"""Vitrea base entity class."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VitreaCoordinator


class VitreaEntity(CoordinatorEntity[VitreaCoordinator]):
    """Base entity for Vitrea integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VitreaCoordinator,
        config_entry: ConfigEntry,
        unique_id: str,
        name: str | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, unique_id)},
            "name": name,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to events when entity is added to hass."""
        await super().async_added_to_hass()
        # Example: subscribe to coordinator updates or events here if needed

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup when entity is removed from hass."""
        await super().async_will_remove_from_hass()
        # Example: cleanup subscriptions or listeners here if needed

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._attr_unique_id in getattr(
            self.coordinator, "data", {}
        )
