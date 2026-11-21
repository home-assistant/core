"""Shared entity base for the Habitron platforms."""

from typing import override

from habitron_client import BusMember, Module, Router, SmartHub

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HbtnCoordinator

type HbtnOwner = Module | Router | SmartHub


class HabitronEntity(CoordinatorEntity[HbtnCoordinator]):
    """Base class for Habitron entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        module: HbtnOwner,
        sensor: BusMember,
        coord: HbtnCoordinator,
        idx: int,
    ) -> None:
        """Bind the entity to one bus member of its owner."""
        super().__init__(coord, context=idx)
        self.idx = idx
        self._module: HbtnOwner = module
        self._sensor_idx = sensor.nmbr
        self._attr_name = sensor.name

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return the device of the entity's owner."""
        return DeviceInfo(identifiers={(DOMAIN, self._module.uid)})

    @property
    @override
    def available(self) -> bool:
        """Return if the owner is reachable; modules go stale on a router error."""
        return super().available and (
            not isinstance(self._module, Module) or self.coordinator.router.sys_ok
        )
