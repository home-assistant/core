"""The Weenect base class."""
from __future__ import annotations

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTRIBUTION, DOMAIN, TRACKER_REMOVED


class WeenectBaseEntity(CoordinatorEntity):
    """Abstract base entity for weenect."""

    def __init__(self, coordinator: DataUpdateCoordinator, tracker_id: int) -> None:
        """Init Base Entity for Weenect entities."""
        super().__init__(coordinator)
        self.id = tracker_id
        data = self.coordinator.data[self.id]
        self._attr_attribution = ATTRIBUTION
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.id))},
            name=str(data["name"]),
            model=str(data["type"]),
            manufacturer="Weenect",
            sw_version=str(data["firmware"]),
        )
        self._attr_extra_state_attributes = {
            "id": self.id,
            "sim": str(data["sim"]),
            "imei": str(data["imei"]),
        }

    async def _async_handle_tracker_removed(self, removed: list[int]) -> None:
        """Remove self if no longer in UpdateCoordinator data."""
        if self.id in removed:
            await self.async_remove()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{self.coordinator.config_entry.entry_id}_{TRACKER_REMOVED}",
                self._async_handle_tracker_removed,
            )
        )
