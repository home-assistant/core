"""Base class for the La Marzocco entities."""

from dataclasses import dataclass, field
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LmApiCoordinator



@dataclass
class LaMarzoccoEntity(CoordinatorEntity[LmApiCoordinator]):
    """Common elements for all entities."""

    entity_description: LaMarzoccoEntityDescription
    _attr_has_entity_name: bool = True

    def __init__(
        self,
        coordinator: LmApiCoordinator,
        entity_description: LaMarzoccoEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._lm_client = self.coordinator.data
        self._attr_unique_id = (
            f"{self._lm_client.serial_number}_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._lm_client.serial_number)},
            name=self._lm_client.machine_name,
            manufacturer="La Marzocco",
            model=self._lm_client.true_model_name,
            serial_number=self._lm_client.serial_number,
            sw_version=self._lm_client.firmware_version,
        )
