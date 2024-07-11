"""Base entity for Traccar Server."""

from __future__ import annotations

from typing import Any

from pytraccar import DeviceModel, GeofenceModel, PositionModel

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TraccarServerCoordinator


class TraccarServerEntity(CoordinatorEntity[TraccarServerCoordinator]):
    """Base entity for Traccar Server."""

    def __init__(
        self,
        coordinator: TraccarServerCoordinator,
        device: DeviceModel,
    ) -> None:
        """Initialize the Traccar Server entity."""
        super().__init__(coordinator)
        self.device_id = device["id"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device["uniqueId"])},
            model=device["model"],
            name=device["name"],
        )
        self._attr_unique_id = device["uniqueId"]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self.coordinator.data and self.device_id in self.coordinator.data)

    @property
    def traccar_device(self) -> DeviceModel:
        """Return the device."""
        return self.coordinator.data[self.device_id]["device"]

    @property
    def traccar_geofence(self) -> GeofenceModel | None:
        """Return the geofence."""
        return self.coordinator.data[self.device_id]["geofence"]

    @property
    def traccar_position(self) -> PositionModel:
        """Return the position."""
        return self.coordinator.data[self.device_id]["position"]

    @property
    def traccar_attributes(self) -> dict[str, Any]:
        """Return the attributes."""
        return self.coordinator.data[self.device_id]["attributes"]

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self.device_id}",
                self.async_write_ha_state,
            )
        )
        await super().async_added_to_hass()
