"""Base entity for Trafikverket Camera."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TVDataUpdateCoordinator


class TrafikverketCameraEntity(CoordinatorEntity[TVDataUpdateCoordinator]):
    """Base entity for Trafikverket Camera."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TVDataUpdateCoordinator,
        entry_id: str,
    ) -> None:
        """Initiate Trafikverket Camera Sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Trafikverket",
            model="v1.0",
            configuration_url="https://api.trafikinfo.trafikverket.se/",
        )


class TrafikverketCameraNonCameraEntity(TrafikverketCameraEntity):
    """Base entity for Trafikverket Camera but for non camera entities."""

    def __init__(
        self,
        coordinator: TVDataUpdateCoordinator,
        entry_id: str,
        description: EntityDescription,
    ) -> None:
        """Initiate Trafikverket Camera Sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}-{description.key}"
        self.entity_description = description
        self._update_attr()

    @callback
    def _update_attr(self) -> None:
        """Update _attr."""

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_attr()
        return super()._handle_coordinator_update()
