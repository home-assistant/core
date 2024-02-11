"""Base class for the La Marzocco entities."""

from collections.abc import Callable
from dataclasses import dataclass

from lmcloud import LMCloud as LaMarzoccoClient

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaMarzoccoUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoEntityDescription(EntityDescription):
    """Description for all LM entities."""

    available_fn: Callable[[LaMarzoccoClient], bool] = lambda _: True
    supported_fn: Callable[[LaMarzoccoUpdateCoordinator], bool] = lambda _: True


class LaMarzoccoEntity(CoordinatorEntity[LaMarzoccoUpdateCoordinator]):
    """Common elements for all entities."""

    entity_description: LaMarzoccoEntityDescription
    _attr_has_entity_name = True

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.lm
        )

    def __init__(
        self,
        coordinator: LaMarzoccoUpdateCoordinator,
        entity_description: LaMarzoccoEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        lm = coordinator.lm
        self._attr_unique_id = f"{lm.serial_number}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, lm.serial_number)},
            name=lm.machine_name,
            manufacturer="La Marzocco",
            model=lm.true_model_name,
            serial_number=lm.serial_number,
            sw_version=lm.firmware_version,
        )
