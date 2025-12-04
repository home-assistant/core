"""Base entity for Duosida EV Charger."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import DuosidaDataUpdateCoordinator


class DuosidaEntity(CoordinatorEntity[DuosidaDataUpdateCoordinator]):
    """Base class for Duosida entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DuosidaDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        data = coordinator.data or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=f"{NAME} {coordinator.charger.host}",
            manufacturer=data.get("manufacturer") or "Duosida",
            model=data.get("model") or "SmartChargePI",
            sw_version=data.get("firmware"),
        )
