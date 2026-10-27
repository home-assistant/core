"""The LoJack integration entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LoJackCoordinator, get_device_name


class LoJackEntity(CoordinatorEntity[LoJackCoordinator]):
    """Base entity for LoJack entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LoJackCoordinator,
        entity_description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        vehicle = coordinator.vehicle
        if entity_description is None:
            self._attr_unique_id = vehicle.id
        else:
            self.entity_description = entity_description
            self._attr_unique_id = f"{vehicle.id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.id)},
            name=get_device_name(vehicle),
            manufacturer="Spireon LoJack",
            model=vehicle.model,
            serial_number=vehicle.vin,
        )
