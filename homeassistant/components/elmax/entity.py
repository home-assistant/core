"""Elmax integration common classes and utilities."""

from __future__ import annotations

from elmax_api.model.endpoint import DeviceEndpoint

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ElmaxCoordinator


class ElmaxEntity(CoordinatorEntity[ElmaxCoordinator]):
    """Wrapper for Elmax entities."""

    def __init__(
        self,
        elmax_device: DeviceEndpoint,
        panel_version: str,
        coordinator: ElmaxCoordinator,
    ) -> None:
        """Construct the object."""
        super().__init__(coordinator=coordinator)
        self._device = elmax_device
        self._attr_unique_id = elmax_device.endpoint_id
        self._attr_name = elmax_device.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.panel_entry.hash)},
            name=coordinator.panel_entry.get_name_by_user(
                coordinator.http_client.get_authenticated_username()
            ),
            manufacturer="Elmax",
            model=panel_version,
            sw_version=panel_version,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.panel_entry.online
