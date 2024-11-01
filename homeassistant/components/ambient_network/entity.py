"""Base entity class for the Ambient Weather Network integration."""

from __future__ import annotations

from abc import abstractmethod

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AmbientNetworkDataUpdateCoordinator


class AmbientNetworkEntity(CoordinatorEntity[AmbientNetworkDataUpdateCoordinator]):
    """Entity class for Ambient network devices."""

    _attr_attribution = "Data provided by ambientnetwork.net"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AmbientNetworkDataUpdateCoordinator,
        description: EntityDescription,
        mac_address: str,
    ) -> None:
        """Initialize the Ambient network entity."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mac_address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name=coordinator.station_name,
            identifiers={(DOMAIN, mac_address)},
            manufacturer="Ambient Weather",
        )
        self._update_attrs()

    @abstractmethod
    def _update_attrs(self) -> None:
        """Update state attributes."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the state."""

        self._update_attrs()
        super()._handle_coordinator_update()
