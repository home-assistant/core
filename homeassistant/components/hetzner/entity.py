"""Base entity for the Hetzner Cloud integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HetznerCoordinator


class HetznerEntity(CoordinatorEntity[HetznerCoordinator]):
    """Base class for Hetzner Cloud entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HetznerCoordinator,
        lb_id: int,
    ) -> None:
        """Initialize the Hetzner entity."""
        super().__init__(coordinator)
        self.lb_id = lb_id
        lb = coordinator.data[lb_id]
        lb_type = lb.data_model.load_balancer_type
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(lb_id))},
            manufacturer="Hetzner",
            model=lb_type.description if lb_type else None,
            name=lb.data_model.name,
        )
