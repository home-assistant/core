"""Base class for the La Marzocco entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from lmcloud.const import FirmwareType
from lmcloud.models import LaMarzoccoDeviceConfig

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaMarzoccoUpdateCoordinator, _DeviceT

_ConfigT = TypeVar("_ConfigT", bound=LaMarzoccoDeviceConfig)


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoEntityDescription(EntityDescription, Generic[_DeviceT]):
    """Description for all LM entities."""

    available_fn: Callable[[_DeviceT], bool] = lambda _: True
    supported_fn: Callable[[LaMarzoccoUpdateCoordinator[_DeviceT]], bool] = (
        lambda _: True
    )


class LaMarzoccoBaseEntity(
    CoordinatorEntity[LaMarzoccoUpdateCoordinator[_DeviceT]],
    Generic[_DeviceT],
):
    """Common elements for all entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LaMarzoccoUpdateCoordinator[_DeviceT],
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


class LaMarzoccoEntity(LaMarzoccoBaseEntity[_DeviceT], Generic[_DeviceT]):
    """Common elements for all entities."""

    entity_description: LaMarzoccoEntityDescription[_DeviceT]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.device
        )

    def __init__(
        self,
        coordinator: LaMarzoccoUpdateCoordinator[_DeviceT],
        entity_description: LaMarzoccoEntityDescription[_DeviceT],
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description
