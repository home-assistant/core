"""Base class for the La Marzocco entities."""

from collections.abc import Callable
from dataclasses import dataclass

from lmcloud.const import FirmwareType
from lmcloud.lm_machine import LaMarzoccoMachine

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaMarzoccoMachineUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoEntityDescription(EntityDescription):
    """Description for all LM entities."""

    available_fn: Callable[[LaMarzoccoMachine], bool] = lambda _: True
    supported_fn: Callable[[LaMarzoccoMachineUpdateCoordinator], bool] = lambda _: True


class LaMarzoccoBaseEntity(CoordinatorEntity[LaMarzoccoMachineUpdateCoordinator]):
    """Common elements for all entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LaMarzoccoMachineUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device.serial_number}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial_number)},
            name=device.name,
            manufacturer="La Marzocco",
            model=device.full_model_name,
            serial_number=device.serial_number,
            sw_version=device.firmware[FirmwareType.MACHINE].current_version,
        )


class LaMarzoccoEntity(LaMarzoccoBaseEntity):
    """Common elements for all entities."""

    entity_description: LaMarzoccoEntityDescription

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.device
        )

    def __init__(
        self,
        coordinator: LaMarzoccoMachineUpdateCoordinator,
        entity_description: LaMarzoccoEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description
