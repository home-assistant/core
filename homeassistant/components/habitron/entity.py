"""Shared entity base for the Habitron platforms."""

from typing import override

from habitron_client import BusMember, Module, Router, SmartHub

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HbtnCoordinator

# What an entity can belong to. The three carry no common base in the library,
# but each of them owns a uid and lists of bus members, which is all an entity
# needs -- so one base serves the hub, the router and every module alike.
type HbtnOwner = Module | Router | SmartHub


class HabitronEntity(CoordinatorEntity[HbtnCoordinator]):
    """Base for every coordinator-driven Habitron entity.

    Carries what does not depend on the platform: the owner and the bus member
    the entity is bound to, the member's name, and the link to the owner's
    device in the registry.
    """

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
        """Return information to link this entity with the correct device.

        All Habitron entities live underneath the device identified by
        ``(DOMAIN, uid)`` -- the hub, the router or a module.
        """
        return DeviceInfo(identifiers={(DOMAIN, self._module.uid)})

    @property
    @override
    def available(self) -> bool:
        """Whether the entity's owner can be reached.

        A router reporting a system error cannot reach its modules, so their
        readings are stale. The router's own and the hub's readings still come
        in, and they are what shows the fault, so those stay available.
        """
        return super().available and (
            not isinstance(self._module, Module) or self.coordinator.router.sys_ok
        )
