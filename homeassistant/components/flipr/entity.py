"""Base entity for the flipr entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import BaseDataUpdateCoordinator


class FliprEntity(CoordinatorEntity[BaseDataUpdateCoordinator]):
    """Implements a common class elements representing the Flipr component."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BaseDataUpdateCoordinator,
        description: EntityDescription,
        is_flipr_hub: bool = False,
    ) -> None:
        """Initialize Flipr sensor."""
        super().__init__(coordinator)
        self.device_id = coordinator.device_id
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}-{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer=MANUFACTURER,
            name=f"Flipr hub {self.device_id}"
            if is_flipr_hub
            else f"Flipr {self.device_id}",
        )
