"""Base entity for the Duosida EV Charger integration."""

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DuosidaCoordinator


class DuosidaEntity(CoordinatorEntity[DuosidaCoordinator]):
    """Base class for Duosida entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DuosidaCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        device_id = coordinator.config_entry.unique_id
        if TYPE_CHECKING:
            assert device_id is not None
        info = coordinator.info
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=info.manufacturer or "Duosida",
            model=info.model or None,
            name=coordinator.config_entry.title,
            serial_number=device_id,
            sw_version=info.firmware or None,
        )
